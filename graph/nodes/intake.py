"""Route using a cheap catalog; chat never triggers a full data scan."""
import json
from uuid import uuid4
from langchain_core.messages import AIMessage
from graph.state import RouteDecision
from graph.llms import get_node_llm
from graph.prompts import router_prompt
from graph.utils import format_history, latest_human_message
from graph.recovery import model_failure

def intake_node(state):
    reset = {"schema_version": 2, "plan": {}, "plan_version": 0, "current_step_index": 0,
             "step_results": [], "plan_history": [], "attempt_history": [], "code": None,
             "execution_status": None, "execution_output": None, "execution_error": None,
             "traceback": None, "debug_count": 0, "replan_count": 0, "answer_revision_count": 0,
             "replan_reason": None, "verification": None, "draft_answer": None,
             "clarification_question": None, "artifacts": [], "artifact_run_id": uuid4().hex,
             "final_answer": None, "workflow_status": "running", "node_error": None,
             "termination_reason": None, "route": "failed"}
    try:
        from graph.sources import source_catalog
        catalog = source_catalog(state)
        result = (router_prompt | get_node_llm("router").with_structured_output(RouteDecision)).invoke({
            "history": format_history(state["messages"], exclude_last=True) + "\nPreviously resolved request:\n" + state.get("analysis_memory", ""),
            "current_question": latest_human_message(state["messages"]),
            "profile_summary": json.dumps(catalog, ensure_ascii=False),
        })
        reset.update(route={"chat": "chat", "analysis": "analysis", "clarify_needed": "clarify"}[result.intent],
                     analysis_request=result.analysis_request or latest_human_message(state["messages"]),
                     analysis_columns=result.columns)
        if result.intent != "analysis" and result.response:
            reset.update(route="done", final_answer=result.response, messages=[AIMessage(content=result.response)],
                         workflow_status="success" if result.intent == "chat" else "needs_input")
        return reset
    except Exception as exc:
        return {**reset, **model_failure("Intake", exc)}

def after_intake(state):
    return "finalize" if state.get("workflow_status") == "failed" else state["route"]
