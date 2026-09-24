from graph.state import DataAgentState


def router_after_action(state: DataAgentState) -> str:
    mode = state.get("action", {}).get("mode")
    if mode == "done":
        return "synthetic"
    if mode == "code":
        return "coder"
    return "tool_executor"
