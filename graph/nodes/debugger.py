from functools import lru_cache

from configuration import DEBUGGER_LLM_ENABLED
from graph.state import DataAgentState


@lru_cache(maxsize=1)
def _debug_chain():
    from graph.llms import get_node_llm
    from graph.prompts import debugger_prompt

    return debugger_prompt | get_node_llm("debugger")


def _deterministic_feedback(state: DataAgentState) -> str:
    error_type = state.get("execution_error") or "UnknownError"
    guidance = {
        "SyntaxError": "Sửa đúng dòng cú pháp được nêu trong lỗi rồi chạy lại.",
        "ValueError": (
            "Tuân thủ policy import/đường dẫn của executor và dùng đúng CSV/artifacts "
            "đã được cung cấp."
        ),
        "TimeoutExpired": (
            "Giảm độ phức tạp, tránh loop không giới hạn và chỉ đọc các cột cần thiết."
        ),
        "OutputLimitExceeded": (
            "Chỉ print số liệu tổng hợp cần cho câu trả lời; không print toàn bộ DataFrame."
        ),
        "ArtifactLimitExceeded": (
            "Giảm số lượng/kích thước artifact và chỉ tạo file người dùng yêu cầu."
        ),
        "MissingExecutionOutput": (
            "Thêm print cho kết quả phân tích hoặc lưu artifact hợp lệ."
        ),
        "SubprocessError": (
            "Đọc traceback, sửa exception gốc và giữ code độc lập cho lần chạy mới."
        ),
    }.get(
        error_type,
        "Sửa exception gốc trong traceback và giữ code độc lập cho lần chạy mới.",
    )
    return f"{error_type}: {guidance}"


def debug_node(state: DataAgentState):
    feedback = _deterministic_feedback(state)
    if DEBUGGER_LLM_ENABLED:
        try:
            response = _debug_chain().invoke({
                "code": state.get("code"),
                "execution_error": state.get("execution_error"),
                "traceback": state.get("traceback"),
            })
            feedback = response.content
        except Exception:
            pass

    return {
        "debug_feedback": feedback,
        "retry_count": state.get("retry_count", 0) + 1,
    }
