# from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.state import DataAgentState
from graph.nodes import (
    clarify_node,
    coder_node,
    debug_node,
    execution_node,
    extract_schema_node,
    planner_node,
    synthetic_node,
    validate_node,
    chat_node
)
from graph.edges import (
    question_router,
    router_after_execute,
    router_after_validation,
)

def build_graph():
    graph = StateGraph(DataAgentState)

    # --- Đăng ký nodes ---
    graph.add_node("extract_schema", extract_schema_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("chat", chat_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("execute", execution_node)
    graph.add_node("debug", debug_node)
    graph.add_node("synthetic", synthetic_node)
    graph.add_node("validate", validate_node)

    # --- Luồng đi ---
    graph.add_edge(START, "extract_schema")

    graph.add_conditional_edges("extract_schema", question_router, {
        "analysis": "planner",
        "clarify": "clarify",
        "chat": "chat",
    })
    graph.add_edge("clarify", END)
    graph.add_edge("chat", END)

    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "execute")

    graph.add_conditional_edges("execute", router_after_execute, {
        "coder": "coder",          # step thành công, còn step tiếp theo
        "debug": "debug",          # lỗi, còn lượt retry
        "planner": "planner",      # hết retry -> replan
        "synthetic": "synthetic",  # hết step (hoặc best-effort)
    })
    graph.add_edge("debug", "coder")

    graph.add_edge("synthetic", "validate")
    graph.add_conditional_edges("validate", router_after_validation, {
        "planner": "planner",
        "end": END,
    })

    # return graph.compile(checkpointer=MemorySaver())
    return graph.compile()

app = build_graph()