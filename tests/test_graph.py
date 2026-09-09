from pathlib import Path
import pytest
from langchain_core.messages import HumanMessage
from conftest import plan, verdict

def test_analysis_publishes_only_verified_answer(agent, request_state):
    app, models = agent
    result = app.invoke(request_state)
    assert models.calls == ["router", "planner", "coder", "synthetic", "verification"]
    assert result["step_results"][0]["value"] == 30
    assert result["workflow_status"] == "success"
    assert result["final_answer"] == result["messages"][-1].content
    assert len(result["messages"]) == 2
    assert "Tính tổng Sales" in models.prompts["verification"][0]

@pytest.mark.parametrize("intent", ["chat", "clarify_needed"])
def test_non_analysis_ends_directly(agent, request_state, intent):
    app, models = agent
    models.set("router", {"intent": intent})
    result = app.invoke(request_state)
    assert "coder" not in models.calls
    assert "verification" not in models.calls
    assert result["final_answer"]

def test_missing_csv_clarifies(agent):
    app, models = agent
    result = app.invoke({"messages": [HumanMessage(content="Analyze")]})
    assert result["workflow_status"] == "needs_input"
    assert "planner" not in models.calls

def two_steps():
    first = plan()["steps"][0]
    first["expected_output"] = {"type": "table", "columns": ["Sales"], "description": "Numeric Sales"}
    first["goal"] = "Prepare numeric Sales"
    second = {"step": 2, "goal": "Sum prepared Sales",
              "inputs": [{"source": "step_1", "columns": ["Sales"]}], "operation": "Sum",
              "expected_output": {"type": "scalar", "columns": [], "description": "Total Sales"}}
    return plan([first, second])

def test_steps_pass_parquet_and_do_not_repeat_previous_code(agent, request_state):
    app, models = agent
    models.set("planner", two_steps())
    models.set("coder",
        {"code": "import pandas as pd\nsave_table(pd.DataFrame({'Sales': pd.to_numeric(load_input('dataset_1')['Sales'])}))"},
        {"code": "save_scalar(load_input('step_1')['Sales'].sum())"})
    models.set("verification", verdict(refs=["step_2"]))
    result = app.invoke(request_state)
    assert [r["type"] for r in result["step_results"]] == ["table", "scalar"]
    assert result["step_results"][-1]["value"] == 30
    assert models.calls.count("coder") == 2
    assert result["step_results"][0]["path"].endswith(".parquet")
    assert len(result["attempt_history"]) == 2

def test_debug_only_repairs_current_step(agent, request_state):
    app, models = agent
    models.set("coder", {"code": "raise ValueError('broken')"})
    result = app.invoke(request_state)
    assert models.calls.count("coder") == 1
    assert models.calls.count("debugger") == 1
    assert [a["attempt"] for a in result["attempt_history"]] == [0, 1]
    assert result["step_results"][0]["value"] == 30

def test_exhaustion_three_runs_per_plan_two_plans(agent, request_state):
    app, models = agent
    broken = {"code": "raise ValueError('still broken')"}
    models.set("coder", broken, broken)
    models.set("debugger", broken, broken, broken, broken)
    result = app.invoke(request_state)
    assert len(result["attempt_history"]) == 6
    assert [a["attempt"] for a in result["attempt_history"]] == [0, 1, 2, 0, 1, 2]
    assert result["replan_count"] == 1
    assert models.calls.count("planner") == 2
    assert result["workflow_status"] == "failed"
    assert result["artifacts"] == []
    assert "verification" not in models.calls
    assert "still broken" in models.prompts["planner"][-1]

def test_replan_drops_old_successful_outputs(agent, request_state, monkeypatch):
    import configuration as cfg
    monkeypatch.setattr(cfg, "MAX_DEBUG_RETRIES_PER_STEP", 0)
    app, models = agent
    models.set("planner", two_steps(), plan())
    models.set("coder",
        {"code": "from pathlib import Path\nimport pandas as pd\nPath(ARTIFACTS_DIR,'old.csv').write_text('old')\nsave_table(pd.DataFrame({'Sales':[10,20]}))"},
        {"code": "raise ValueError('rethink this')"},
        {"code": "save_scalar(30)"})
    result = app.invoke(request_state)
    assert result["workflow_status"] == "success"
    assert len(result["step_results"]) == 1
    assert result["step_results"][0]["plan_version"] == 1
    assert result["plan_history"][0]["step_results"][0]["artifacts"]
    assert result["artifacts"] == []
    assert "old.csv" not in models.prompts["synthetic"][-1]

def test_answer_revision_reuses_results(agent, request_state):
    app, models = agent
    models.set("synthetic", {"final_answer": "Wrong draft"}, {"final_answer": "Correct final"})
    models.set("verification", verdict("revise_answer"), verdict())
    result = app.invoke(request_state)
    assert models.calls.count("coder") == 1
    assert models.calls.count("synthetic") == 2
    assert result["answer_revision_count"] == 1
    assert result["final_answer"] == "Correct final"
    assert all(m.content != "Wrong draft" for m in result["messages"])

def test_repeated_answer_rejection_fails(agent, request_state):
    app, models = agent
    models.set("verification", verdict("revise_answer"), verdict("revise_answer"))
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert models.calls.count("synthetic") == 2
    assert models.calls.count("planner") == 1

def test_verification_can_replan(agent, request_state):
    app, models = agent
    models.set("verification", verdict("replan"), verdict())
    result = app.invoke(request_state)
    assert result["workflow_status"] == "success"
    assert models.calls.count("coder") == 2
    assert result["plan_version"] == 1
    assert result["answer_revision_count"] == 0

def test_verification_replan_budget_exhausted(agent, request_state):
    app, models = agent
    models.set("verification", verdict("replan"), verdict("replan"))
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert result["artifacts"] == []
    assert models.calls.count("planner") == 2

@pytest.mark.parametrize("node", ["planner", "verification"])
def test_semantic_clarification_bypasses_extra_model(agent, request_state, node):
    app, models = agent
    if node == "planner":
        models.set("planner", {"steps": [], "success_criteria": [], "clarification_question": "Which metric?"})
    else:
        models.set("verification", verdict("clarify"))
    result = app.invoke(request_state)
    assert result["workflow_status"] == "needs_input"
    assert "clarify" not in models.calls
    assert len(result["messages"]) == 2

@pytest.mark.parametrize("node", ["planner", "coder", "debugger", "synthetic", "verification"])
def test_model_outage_terminates_without_replan(agent, request_state, node):
    app, models = agent
    if node == "debugger":
        models.set("coder", {"code": "raise ValueError('broken')"})
    models.set(node, RuntimeError("model offline"))
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert result["replan_count"] == 0
    assert "model offline" in result["final_answer"]


def test_planner_provider_value_error_does_not_replan(agent, request_state):
    app, models = agent
    models.set("planner", ValueError("invalid provider configuration"))
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert result["replan_count"] == 0
    assert models.calls.count("planner") == 1

@pytest.mark.parametrize("node", ["coder", "debugger", "synthetic", "verification"])
def test_bad_structured_output_fails_cleanly(agent, request_state, node):
    app, models = agent
    if node == "debugger":
        models.set("coder", {"code": "raise ValueError('broken')"})
    models.set(node, {})
    assert app.invoke(request_state)["workflow_status"] == "failed"

@pytest.mark.parametrize("bad", ["future", "unknown_column", "numbering", "empty"])
def test_bad_plan_consumes_replan_budget(agent, request_state, bad):
    app, models = agent
    value = plan()
    if bad == "future":
        value["steps"][0]["inputs"][0]["source"] = "step_2"
    elif bad == "unknown_column":
        value["steps"][0]["inputs"][0]["columns"] = ["not_a_column"]
    elif bad == "numbering":
        value["steps"][0]["step"] = 2
    else:
        value = {}
    models.set("planner", value, value)
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert models.calls.count("planner") == 2
    assert "coder" not in models.calls

def test_unsupported_verifier_pass_is_rejected(agent, request_state):
    app, models = agent
    models.set("verification", verdict(refs=["step_99"]))
    assert app.invoke(request_state)["workflow_status"] == "failed"

def test_new_turn_resets_counters_and_preserves_context(agent, request_state):
    app, models = agent
    first = app.invoke(request_state)
    second = app.invoke({**first, "messages": [*first["messages"], HumanMessage(content="And by City?")]})
    assert second["profile_cache_key"] == first["profile_cache_key"]
    assert second["artifact_run_id"] != first["artifact_run_id"]
    assert len(second["attempt_history"]) == 1
    assert "Tính tổng Sales" in models.prompts["verification"][-1]
    assert "And by City?" in models.prompts["verification"][-1]

def test_zero_recovery_budgets(agent, request_state, monkeypatch):
    import configuration as cfg
    monkeypatch.setattr(cfg, "MAX_REPLANS", 0)
    monkeypatch.setattr(cfg, "MAX_DEBUG_RETRIES_PER_STEP", 0)
    app, models = agent
    models.set("coder", {"code": "raise ValueError('stop')"})
    result = app.invoke(request_state)
    assert len(result["attempt_history"]) == 1
    assert models.calls == ["router", "planner", "coder"]
    assert result["workflow_status"] == "failed"


def test_maximum_loops_fit_recursion_limit(agent, request_state, monkeypatch):
    """Exercise every allowed debug and revision across two six-step plans."""
    import json
    import configuration as cfg
    from graph.nodes import execution
    from graph.runtime import read_result
    from graph.utils import current_step, get_attempt_artifacts_dir
    app, models = agent
    steps = []
    for number in range(1, cfg.PLAN_MAX_STEPS + 1):
        step = plan()["steps"][0]
        step["step"] = number
        if number > 1:
            step["inputs"] = [{"source": f"step_{number - 1}", "columns": []}]
        steps.append(step)
    models.set("planner", plan(steps), plan(steps))
    models.set("verification", verdict("revise_answer"), verdict("replan"),
               verdict("revise_answer"), verdict())

    def controlled_execution(state):
        if state["debug_count"] < cfg.MAX_DEBUG_RETRIES_PER_STEP:
            return {"execution_status": "error", "execution_error": "ControlledError",
                    "execution_output": "", "traceback": "Try again"}
        directory = get_attempt_artifacts_dir(state)
        directory.mkdir(parents=True)
        (directory / "result.json").write_text(json.dumps({"type": "scalar", "value": 30}))
        return {"execution_status": "success", "execution_error": None,
                "execution_output": "", "traceback": None,
                "result": read_result(directory, current_step(state)["expected_output"])}

    monkeypatch.setattr(execution, "run_python", controlled_execution)
    result = app.invoke(request_state)
    assert result["workflow_status"] == "success"
    assert len(result["attempt_history"]) == 36
    assert models.calls.count("debugger") == 24
    assert models.calls.count("synthetic") == 4
    assert models.calls.count("verification") == 4


def test_invalid_replan_clears_previous_evidence(agent, request_state):
    app, models = agent
    models.set("verification", verdict("replan"))
    models.set("planner", plan(), {})
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert result["step_results"] == []
    assert len(result["plan_history"][0]["step_results"]) == 1


@pytest.mark.parametrize("kind", ["result", "artifact"])
def test_changed_evidence_cannot_pass_verification(agent, request_state, monkeypatch, kind):
    import json
    import configuration as cfg
    from graph.nodes.verification import verification_node
    monkeypatch.setattr(cfg, "MAX_REPLANS", 0)
    app, models = agent
    models.set("coder", {"code": "from pathlib import Path\nPath(ARTIFACTS_DIR,'report.csv').write_text('original')\nsave_scalar(30)"})
    state = app.invoke(request_state)
    directory = Path(state["step_results"][0]["directory"])
    if kind == "result":
        (directory / "result.json").write_text(json.dumps({"type": "scalar", "value": 999}))
    else:
        (directory / "report.csv").write_text("changed")
    before = models.calls.count("verification")
    update = verification_node(state)
    assert update["workflow_status"] == "failed"
    assert models.calls.count("verification") == before


def test_real_graph_import_needs_no_key_network_or_diagram_write():
    import os
    import subprocess
    import sys
    from graph.utils import get_project_root
    root = get_project_root()
    before = (root / "flow.png").read_bytes()
    script = (
        "import socket\n"
        "def forbidden(*args, **kwargs): raise AssertionError('network during import')\n"
        "socket.socket.connect = forbidden\n"
        "from graph.graph import app\n"
        "assert 'verification' in app.get_graph().nodes\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in {
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY"}}
    process = subprocess.run([sys.executable, "-c", script], cwd=root, env=env,
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    assert (root / "flow.png").read_bytes() == before
