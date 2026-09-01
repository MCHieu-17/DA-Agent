from langchain_core.messages import AIMessage

from configuration import MAX_REPLANS, MAX_RETRIES
from graph.state import DataAgentState


def failure_node(state: DataAgentState):
    """Finish the graph with an explicit, user-visible failure state."""
    if state.get("node_error"):
        reason = "Một node AI không thể tạo đầu ra hợp lệ sau khi gọi model."
    elif state.get("execution_status") == "error":
        detail = state.get("execution_error") or "Lỗi không xác định"
        reason = (
            "Không thể thực thi kế hoạch phân tích sau khi đã dùng hết "
            f"{state.get('max_retries', MAX_RETRIES)} lần retry và "
            f"{state.get('max_replans', MAX_REPLANS)} lần replan. Lỗi cuối: {detail}"
        )
    elif state.get("is_sufficient") is False:
        reason = (
            "Không thể tạo câu trả lời đạt yêu cầu sau khi đã dùng hết "
            f"{state.get('max_replans', MAX_REPLANS)} lần replan. "
            f"Đánh giá cuối: {state.get('validation_feedback') or 'Không đủ bằng chứng.'}"
        )
    else:
        reason = "Workflow dừng vì trạng thái execute không hợp lệ."

    answer = f"Phân tích chưa hoàn tất. {reason}"
    return {
        "workflow_status": "failed",
        "failure_reason": reason,
        "final_answer": answer,
        "messages": [AIMessage(content=answer)],
    }
