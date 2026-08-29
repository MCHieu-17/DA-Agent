from graph.state import DataAgentState

def router_after_execute(state: DataAgentState) -> str:
    status = state.get("execution_status")
    
    if status == "error":
        # 1. Còn lượt retry -> debug
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "debug"
            
        # 2. Hết retry nhưng còn replan -> planner (đổi chiến thuật)
        elif state.get("replan_count", 0) < state.get("max_replans", 3):
            return "planner"
            
        # 3. Cạn tài nguyên -> vẫn tổng hợp (best-effort) thay vì dừng đột ngột
        else:
            return "synthetic"

    elif status == "success":
        plan = state.get("plan", [])
        current_idx = state.get("current_step_idx", 0)
        
        # 1. Còn bước -> coder
        if current_idx < len(plan):
            return "coder"
            
        # 2. Hết bước -> synthetic để tạo câu trả lời
        else:
            return "synthetic"
    
    # Fallback
    return "synthetic"