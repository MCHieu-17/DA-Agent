from langgraph.graph import END
from graph.state import DataAgentState

def route_after_execute(state: DataAgentState) -> str:
    status = state.get("execution_status")
    
    # ==========================================
    # NHÁNH 1: NẾU THỰC THI BỊ LỖI
    # ==========================================
    if status == "error":
        # 1. Còn lượt retry -> Chuyển cho Debug để phân tích và sửa
        # Lưu ý: retry_count đã được cộng 1 từ bên trong node Executor
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "debug"
            
        # 2. Hết retry nhưng còn lượt replan -> Chuyển về Planner để đổi chiến thuật
        elif state.get("replan_count", 0) < state.get("max_replans", 3):
            return "planner"
            
        # 3. Hết toàn bộ tài nguyên -> Dừng hệ thống (chấp nhận thất bại)
        else:
            return END

    # ==========================================
    # NHÁNH 2: NẾU THỰC THI THÀNH CÔNG
    # ==========================================
    elif status == "success":
        plan = state.get("plan", [])
        current_idx = state.get("current_step_idx", 0)
        
        # 1. Nếu vẫn còn bước chưa làm -> Quay lại Coder cho bước tiếp theo
        if current_idx < len(plan):
            return "coder"
            
        # 2. Đã làm hết tất cả các bước -> Kết thúc đồ thị thành công
        else:
            return END
            
    # Fallback an toàn nếu status không xác định
    return END