# nodes/router_after_validation.py
from langgraph.graph import END
from graph.state import DataAgentState


def router_after_validation(state: DataAgentState) -> str:
    """Điều hướng luồng đi sau node validate."""
    # 1. Câu trả lời đã đạt yêu cầu -> kết thúc
    if state.get("is_sufficient"):
        return "end"

    # 2. Đã replan quá giới hạn -> kết thúc, tránh vòng lặp vô hạn
    if state.get("replan_count", 0) >= state.get("max_replans", 3):
        return "end"

    # 3. Chưa đạt -> quay về planner để bổ sung/điều chỉnh bước
    return "planner"