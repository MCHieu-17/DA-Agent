from configuration import MAX_REPLANS, MAX_RETRIES
from graph.state import DataAgentState

def router_after_execute(state: DataAgentState) -> str:
    status = state.get("execution_status")

    if status == "error":
        # retry_count counts debug/retry attempts, not the initial execution.
        if state.get("retry_count", 0) < state.get("max_retries", MAX_RETRIES):
            return "debug"

        # 2. Hết retry nhưng còn replan -> planner (đổi chiến thuật)
        elif state.get("replan_count", 0) < state.get("max_replans", MAX_REPLANS):
            return "planner"

        # 3. Cạn tài nguyên -> thất bại rõ ràng, không tổng hợp số liệu thiếu căn cứ.
        else:
            return "failure"

    elif status == "success":
        plan = state.get("plan", [])
        current_idx = state.get("current_step_idx", 0)

        # 1. Còn bước -> coder
        if current_idx < len(plan):
            return "coder"

        # 2. Hết bước -> synthetic để tạo câu trả lời
        else:
            return "synthetic"

    # Unknown/missing execution state is an internal workflow failure.
    return "failure"
