<<<<<<< HEAD
"""Sequential analysis with bounded debug, replan, and answer revisions."""
from langgraph.graph import END, START, StateGraph
from configuration import GRAPH_RECURSION_LIMIT
from graph.state import DataAgentState
from graph.nodes.data_profiling import data_profiling_node
from graph.nodes.planner import planner_node
from graph.nodes.coder import coder_node
from graph.nodes.execution import execution_node
from graph.nodes.debugger import debug_node
from graph.nodes.synthetic import synthetic_node
from graph.nodes.verification import verification_node
from graph.nodes.finalize import finalize_node
from graph.nodes.chat import chat_node
from graph.nodes.clarifier import clarify_node
from graph.nodes.intake import intake_node, after_intake

def after_profile(state):
    if state.get("workflow_status") == "failed":
        return "finalize"
    return "planner" if state.get("profile_valid") else "clarify"

def after_planner(state):
    if state.get("workflow_status") == "failed":
        return "finalize"
    if state.get("clarification_question"):
        return "clarify"
    return "planner" if state.get("replan_reason") else "coder"

def after_code(state):
    return "finalize" if state.get("workflow_status") == "failed" else "execute"

def after_execute(state):
    if state.get("workflow_status") == "failed":
        return "finalize"
    if state.get("replan_reason"):
        return "planner"
    if state["execution_status"] == "error":
        return "debug"
    return "coder" if state["current_step_index"] < len(state["plan"]["steps"]) else "synthetic"

def after_synthetic(state):
    return "finalize" if state.get("workflow_status") == "failed" else "verification"

def after_verification(state):
    if state.get("workflow_status") == "failed":
        return "finalize"
    if state.get("replan_reason"):
        return "planner"
    return {"pass": "finalize", "revise_answer": "synthetic", "clarify": "clarify"}[state["verification"]["decision"]]

def build_graph():
    graph = StateGraph(DataAgentState)
    for name, node in {
        "intake": intake_node, "data_profiling": data_profiling_node, "chat": chat_node, "clarify": clarify_node,
        "planner": planner_node, "coder": coder_node, "execute": execution_node,
        "debug": debug_node, "synthetic": synthetic_node, "verification": verification_node,
        "finalize": finalize_node,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", after_intake,
        {"analysis": "data_profiling", "chat": "chat", "clarify": "clarify", "finalize": "finalize"})
    graph.add_conditional_edges("data_profiling", after_profile,
                                {"planner": "planner", "clarify": "clarify", "finalize": "finalize"})
    for name, router, destinations in [
        ("planner", after_planner, ["finalize", "clarify", "planner", "coder"]),
        ("coder", after_code, ["finalize", "execute"]),
        ("debug", after_code, ["finalize", "execute"]),
        ("execute", after_execute, ["finalize", "planner", "debug", "coder", "synthetic"]),
        ("synthetic", after_synthetic, ["finalize", "verification"]),
        ("verification", after_verification, ["finalize", "planner", "synthetic", "clarify"]),
    ]:
        graph.add_conditional_edges(name, router, {n: n for n in destinations})
    for name in ("chat", "clarify", "finalize"):
        graph.add_edge(name, END)
    return graph.compile().with_config({"recursion_limit": GRAPH_RECURSION_LIMIT})
=======
from langgraph.graph import END, START, StateGraph

from graph.edges import question_router, router_after_action, router_after_execute, router_after_validation
from graph.nodes import action_selector_node, chat_node, cleanup_node, coder_node, debug_node, execution_node, extract_schema_node, planner_node, synthetic_node, tool_executor_node, validate_node
from graph.state import DataAgentState


def build_graph():
    graph = StateGraph(DataAgentState)
    graph.add_node("extract_schema", extract_schema_node)
    graph.add_node("chat", chat_node)
    graph.add_node("planner", planner_node)
    graph.add_node("action_selector", action_selector_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("coder", coder_node)
    graph.add_node("execute", execution_node)
    graph.add_node("debug", debug_node)
    graph.add_node("synthetic", synthetic_node)
    graph.add_node("validate", validate_node)
    graph.add_node("cleanup", cleanup_node)

    graph.add_edge(START, "extract_schema")
    graph.add_conditional_edges("extract_schema", question_router, {"chat": "chat", "analysis": "planner"})
    graph.add_edge("chat", END)
    graph.add_edge("planner", "action_selector")
    graph.add_conditional_edges("action_selector", router_after_action, {"tool_executor": "tool_executor", "coder": "coder", "synthetic": "synthetic"})
    graph.add_edge("tool_executor", "execute")
    graph.add_edge("coder", "execute")
    graph.add_conditional_edges("execute", router_after_execute, {"action_selector": "action_selector", "debug": "debug", "planner": "planner", "synthetic": "synthetic"})
    graph.add_edge("debug", "coder")
    graph.add_edge("synthetic", "validate")
    graph.add_conditional_edges("validate", router_after_validation, {"planner": "planner", "cleanup": "cleanup"})
    graph.add_edge("cleanup", END)
    return graph.compile()

>>>>>>> restore-work

app = build_graph()
