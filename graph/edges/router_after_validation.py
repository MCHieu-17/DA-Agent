from configuration import MAX_REPLANS
from graph.state import DataAgentState


def router_after_validation(state: DataAgentState) -> str:
    """Điều hướng luồng đi sau node validate."""
    if state.get("node_error"):
        return "failure"

    # 1. Câu trả lời đã đạt yêu cầu -> kết thúc
    if state.get("is_sufficient"):
        return "end"

    # 2. Đã dùng hết số lần replan -> kết thúc bằng trạng thái thất bại.
    if state.get("replan_count", 0) >= state.get("max_replans", MAX_REPLANS):
        return "failure"

    # 3. Chưa đạt -> quay về planner để bổ sung/điều chỉnh bước
    return "planner"
