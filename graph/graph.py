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


app = build_graph()
