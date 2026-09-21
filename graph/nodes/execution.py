"""Execute generated Python locally and record every attempt."""

import json
import os
import subprocess
import sys

import configuration as cfg
from graph.recovery import request_replan
from graph.runtime import read_result
from graph.utils import (
    current_step,
    get_attempt_artifacts_dir,
    get_project_root,
    step_inputs,
    truncate_text,
)


def _text(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def _error(name, detail, stdout=""):
    return {
        "execution_status": "error",
        "execution_output": stdout,
        "execution_error": name,
        "traceback": truncate_text(detail, cfg.EXECUTION_ERROR_MAX_CHARS),
    }


def run_python(state):
    code = state.get("code") or ""
    if not code.strip():
        return _error("EmptyCode", "No Python code was generated.")

    directory = get_attempt_artifacts_dir(state)
    try:
        directory.mkdir(parents=True, exist_ok=False)
        context = {
            "inputs": step_inputs(state),
            "expected_output": current_step(state)["expected_output"],
        }
        context_path = directory / "context.json"
        code_path = directory / "code.py"
        context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        code_path.write_text(code, encoding="utf-8")

        environment = os.environ.copy()
        environment.update(
            MPLBACKEND=cfg.EXECUTION_MATPLOTLIB_BACKEND,
            PYTHONUTF8="1",
            PYTHONUNBUFFERED="1",
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "graph.runtime",
                str(context_path),
                str(code_path),
            ],
            cwd=get_project_root(),
            env=environment,
            capture_output=True,
            text=True,
            timeout=cfg.EXECUTION_TIMEOUT_SECONDS,
            check=False,
        )
        (directory / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (directory / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            return _error("SubprocessError", completed.stderr, completed.stdout.strip())
        result = read_result(directory, context["expected_output"])
        return {
            "execution_status": "success",
            "execution_output": completed.stdout.strip(),
            "execution_error": None,
            "traceback": None,
            "result": result,
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = _text(exc.stdout), _text(exc.stderr)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "stdout.log").write_text(stdout, encoding="utf-8")
        (directory / "stderr.log").write_text(stderr, encoding="utf-8")
        return _error(
            "TimeoutExpired",
            f"Python exceeded {cfg.EXECUTION_TIMEOUT_SECONDS} seconds. {stderr}",
            stdout,
        )
    except Exception as exc:
        return _error(type(exc).__name__, str(exc))


def execution_node(state):
    outcome = run_python(state)
    step = current_step(state)
    attempt = {
        "plan_version": state["plan_version"],
        "step": step["step"],
        "attempt": state["debug_count"],
        "directory": str(get_attempt_artifacts_dir(state)),
        "status": outcome["execution_status"],
        "error": outcome["execution_error"],
    }
    update = {key: value for key, value in outcome.items() if key != "result"}
    update["attempt_history"] = [*state.get("attempt_history", []), attempt]

    if outcome["execution_status"] == "success":
        result = {
            "ref": f"step_{step['step']}",
            "step": step["step"],
            "plan_version": state["plan_version"],
            "code": state["code"],
            "directory": attempt["directory"],
            **outcome["result"],
        }
        update.update(
            step_results=[*state.get("step_results", []), result],
            current_step_index=state["current_step_index"] + 1,
            code=None,
            debug_count=0,
        )
    elif state["debug_count"] >= cfg.MAX_DEBUG_RETRIES_PER_STEP:
        update.update(
            request_replan(
                state,
                f"Step {step['step']} failed after debug: {outcome['traceback']}",
            )
        )
    return update
