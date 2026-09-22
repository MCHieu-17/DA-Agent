from graph.state import DataAgentState


def router_after_validation(state: DataAgentState) -> str:
    if state.get("is_sufficient") or state.get("replan_count", 0) >= state.get("max_replans", 2):
        return "cleanup"
    return "planner"
