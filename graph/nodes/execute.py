import io
import traceback
from contextlib import redirect_stdout
from graph.state import DataAgentState

def executor_node(state: DataAgentState):
    code = state.get("code", "")
    current_idx = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"

    # Tạo bộ đệm để hứng toàn bộ lệnh print() từ code
    captured_output = io.StringIO()

    try:
        # Chạy code và điều hướng chuẩn đầu ra (stdout) vào bộ đệm
        with redirect_stdout(captured_output):
            exec(code, globals())
        
        stdout_str = captured_output.getvalue()

        # Đóng gói kết quả thành công để lưu vào lịch sử
        step_result = {
            "step": current_step,
            "code": code,
            "stdout": stdout_str,
            "artifacts": None # Có thể cập nhật sau nếu lưu file ảnh/csv
        }

        return {
            "execution_status": "success",
            "execution_output": stdout_str,
            "past_steps": state.get("past_steps", []) + [step_result],
            "current_step_idx": current_idx + 1 # Chuyển sang bước plan tiếp theo
        }

    except Exception as e:
        # Nếu lỗi, bắt toàn bộ log lỗi để trả về cho Coder sửa
        return {
            "execution_status": "error",
            "execution_error": type(e).__name__,
            "traceback": traceback.format_exc(),
            "retry_count": state.get("retry_count", 0) + 1
        }