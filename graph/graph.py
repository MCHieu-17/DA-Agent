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
from graph.edges.question_router import question_router
from graph.nodes.intake import intake_node, after_intake
from graph.telemetry import observed

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
        graph.add_node(name, observed(name, node))
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", after_intake,
        {"analysis": "data_profiling", "chat": "chat", "clarify": "clarify", "done": END, "finalize": "finalize"})
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

app = build_graph()
