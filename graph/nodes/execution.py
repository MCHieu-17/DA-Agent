import os
import io
import traceback
from contextlib import redirect_stdout
from graph.state import DataAgentState

def execution_node(state: DataAgentState):
    code = state.get("code", "")
    current_idx = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    ARTIFACTS_DIR = state.get("artifacts_dir") or "./artifacts"

    # 1. Đảm bảo thư mục artifacts tồn tại
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    # 2. Chụp trạng thái thư mục artifacts TRƯỚC khi chạy
    files_before = set(os.listdir(ARTIFACTS_DIR))
    captured_output = io.StringIO()

    # 3. Namespace cho exec: inject sẵn ARTIFACTS_DIR để code sinh ra có thể dùng
    exec_globals = {**globals(), "ARTIFACTS_DIR": ARTIFACTS_DIR}

    try:
        with redirect_stdout(captured_output):
            exec(code, exec_globals)
        
        stdout_str = captured_output.getvalue()
        
        # 4. Chụp lại thư mục artifacts SAU khi chạy để tìm file mới
        files_after = set(os.listdir(ARTIFACTS_DIR))
        new_files = list(files_after - files_before)
        artifacts = [
            f"{ARTIFACTS_DIR}/{f}" for f in new_files 
            if f.endswith(('.png', '.jpg', '.jpeg', '.html', '.csv'))
        ]

        step_result = {
            "step": current_step,
            "code": code,
            "stdout": stdout_str,
            "artifacts": artifacts
        }

        return {
            "execution_status": "success",
            "execution_output": stdout_str,
            "past_steps": state.get("past_steps", []) + [step_result],
            "current_step_idx": current_idx + 1,
            "artifacts": state.get("artifacts", []) + artifacts
        }

    except Exception as e:
        return {
            "execution_status": "error",
            "execution_error": type(e).__name__,
            "traceback": traceback.format_exc(),
            "retry_count": state.get("retry_count", 0) + 1
        }