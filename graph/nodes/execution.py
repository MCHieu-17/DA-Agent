"""Execute one step, record an attempt, and publish only successful outputs."""
import json
import os
import subprocess
import sys
import configuration as cfg
from graph.runtime import read_result
from graph.recovery import request_replan, fail
from graph.utils import current_step, get_attempt_artifacts_dir, get_project_root, step_inputs, truncate_text

def _error(error, detail, stdout=""):
    return {"execution_status": "error", "execution_output": stdout,
            "execution_error": error, "traceback": truncate_text(detail, cfg.EXECUTION_ERROR_MAX_CHARS)}

def _text(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""

def run_python(state):
    code = state.get("code") or ""
    if not code.strip():
        return _error("EmptyCode", "No Python code.")
    try:
        directory = get_attempt_artifacts_dir(state)
        directory.mkdir(parents=True, exist_ok=False)
        step = current_step(state)
        context = {"inputs": step_inputs(state), "engine": step.get("engine", "python"),
                   "expected_output": step["expected_output"]}
        import time
        timeout = min(state.get("execution_timeout_seconds", cfg.EXECUTION_TIMEOUT_SECONDS),
                      state.get("deadline", time.time() + 300) - time.time())
        if timeout <= 0:
            raise TimeoutError("Run deadline exceeded.")
        if context["engine"] == "postgres_sql":
            from graph.postgres import execute
            from graph.executors import ExecutionResult
            execute(code, {name: {**spec["broker_source"], "columns": spec["columns"] or spec["broker_source"]["columns"]}
                           for name, spec in context["inputs"].items()}, directory, context["expected_output"])
            completed, result = ExecutionResult(0, "", ""), read_result(directory, context["expected_output"])
        else:
            from graph.executors import execute
            completed, result = execute(directory, context, code, timeout)
        (directory / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (directory / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            from graph.executors import is_transient_bootstrap_error
            if is_transient_bootstrap_error(completed.stderr):
                return _error("RuntimeBootstrapError", completed.stderr, completed.stdout.strip())
            return _error("SubprocessError", completed.stderr, completed.stdout.strip())
        return {"execution_status": "success", "execution_output": completed.stdout.strip(),
                "execution_error": None, "traceback": None, "result": result}
    except subprocess.TimeoutExpired as exc:
        # Timeout streams can be bytes even with text=True.
        (directory / "stdout.log").write_text(_text(exc.stdout), encoding="utf-8")
        (directory / "stderr.log").write_text(_text(exc.stderr), encoding="utf-8")
        return _error("TimeoutExpired", f"Python exceeded timeout. {_text(exc.stderr)}", _text(exc.stdout))
    except Exception as exc:
        return _error(type(exc).__name__, str(exc))

def execution_node(state):
    outcome = run_python(state)
    step = current_step(state)
    attempt = {"plan_version": state["plan_version"], "step": step["step"],
               "attempt": state["debug_count"], "directory": str(get_attempt_artifacts_dir(state)),
               "status": outcome["execution_status"], "error": outcome["execution_error"]}
    update = {k: v for k, v in outcome.items() if k != "result"}
    update["attempt_history"] = [*state.get("attempt_history", []), attempt]
    if outcome["execution_status"] == "success":
        result = {"ref": f"step_{step['step']}", "step": step["step"],
                  "plan_version": state["plan_version"], "code": state["code"],
                  "directory": attempt["directory"], **outcome["result"]}
        update.update(step_results=[*state.get("step_results", []), result],
                      current_step_index=state["current_step_index"] + 1,
                      code=None, debug_count=0)
    elif outcome["execution_error"] in {"ExecutorUnavailable", "PermissionError", "RuntimeBootstrapError"}:
        update.update(fail("Execution infrastructure unavailable: " + outcome["traceback"]))
    elif state["debug_count"] >= cfg.MAX_DEBUG_RETRIES_PER_STEP:
        update.update(request_replan(state, f"Step {step['step']} failed after debug: {outcome['traceback']}"))
    return update
