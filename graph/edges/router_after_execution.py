from graph.state import DataAgentState
from graph.settings import settings


def router_after_execute(state: DataAgentState) -> str:
    if state.get("execution_status") == "error":
        if state.get("action", {}).get("mode") == "tool":
            return "action_selector" if state.get("tool_retry_count", 0) < settings.max_tool_retries else "planner"
        if state.get("retry_count", 0) < state.get("max_retries", 2):
            return "debug"
        return "planner" if state.get("replan_count", 0) < state.get("max_replans", 2) else "synthetic"
    if state.get("current_step_idx", 0) < len(state.get("plan", [])):
        return "action_selector"
    return "synthetic"
