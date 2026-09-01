from graph.state import DataAgentState


def router_after_llm_node(state: DataAgentState) -> str:
    """Stop cleanly if an LLM-backed node could not produce its contract."""
    return "failure" if state.get("node_error") else "continue"
