from graph.state import DataAgentState


def router_after_validation(state: DataAgentState) -> str:
    decision = state.get("validation_decision")
    if decision == "accept":
        return "cleanup"
    if decision == "revise_answer" and state.get("synthesis_retry_count", 0) < state.get("max_synthesis_retries", 2):
        return "synthetic"
    if decision == "reanalyze" and state.get("replan_count", 0) < state.get("max_replans", 2):
        return "planner"
    return "cleanup"
