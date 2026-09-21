"""Route using a cheap catalog; chat never triggers a full data scan."""
import csv
import json
from pathlib import Path
from uuid import uuid4
import configuration as cfg
from graph.state import RouteDecision
from graph.llms import get_node_llm
from graph.prompts import router_prompt
from graph.utils import format_history, latest_human_message
from graph.utils import resolve_project_path
from graph.recovery import model_failure


def _catalog(file_paths):
    catalog = []
    for index, raw_path in enumerate(file_paths, 1):
        path = resolve_project_path(raw_path)
        item = {"dataset_id": f"dataset_{index}", "name": Path(raw_path).name, "columns": []}
        try:
            if path.suffix.lower() not in cfg.CSV_ALLOWED_EXTENSIONS:
                raise ValueError("only .csv files are supported")
            with path.open(encoding=cfg.CSV_READ_OPTIONS["encoding"], newline="") as stream:
                item["columns"] = next(
                    csv.reader(stream, delimiter=cfg.CSV_READ_OPTIONS["sep"]), []
                )
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        catalog.append(item)
    return catalog

def intake_node(state):
    reset = {"plan": {}, "plan_version": 0, "current_step_index": 0,
             "step_results": [], "plan_history": [], "attempt_history": [], "code": None,
             "execution_status": None, "execution_output": None, "execution_error": None,
             "traceback": None, "debug_count": 0, "replan_count": 0, "answer_revision_count": 0,
             "replan_reason": None, "verification": None, "draft_answer": None,
             "clarification_question": None, "artifacts": [], "artifact_run_id": uuid4().hex,
             "final_answer": None, "workflow_status": "running", "node_error": None,
             "termination_reason": None, "route": "failed"}
    try:
        catalog = _catalog(state.get("file_paths", []))
        result = (router_prompt | get_node_llm("router").with_structured_output(RouteDecision)).invoke({
            "history": format_history(state["messages"], exclude_last=True) + "\nPreviously resolved request:\n" + state.get("analysis_memory", ""),
            "current_question": latest_human_message(state["messages"]),
            "profile_summary": json.dumps(catalog, ensure_ascii=False),
        })
        reset.update(route={"chat": "chat", "analysis": "analysis", "clarify_needed": "clarify"}[result.intent],
                     analysis_request=result.analysis_request or latest_human_message(state["messages"]),
                     analysis_columns=result.columns)
        if result.intent == "clarify_needed" and result.response:
            reset["clarification_question"] = result.response
        return reset
    except Exception as exc:
        return {**reset, **model_failure("Intake", exc)}

def after_intake(state):
    return "finalize" if state.get("workflow_status") == "failed" else state["route"]
