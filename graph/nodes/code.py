from graph.state import DataAgentState, CoderOutput
from graph.chains import llm_coder_chain

def coder_node(state: DataAgentState):
    plan = state.get("plan", [])
    current_idx = state.get("current_step_idx", 0)
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    
    schema_str = state.get("schema_str", "")
    past_steps = state.get("past_steps", [])
    code = state.get("code", "")
    traceback = state.get("traceback", "")

    # Phân nhánh logic bằng f-string để tự động điền dữ liệu từ state
    if state.get("execution_status") == "error":
        system_content = "Bạn là chuyên gia Data Engineer. Nhiệm vụ của bạn là SỬA LỖI mã Python dựa trên traceback."
        human_content = f"""
        - Dữ liệu schema: {schema_str}
        - Lịch sử các bước trước: {past_steps}
        - Bước đang thực hiện: {current_step}
        - Mã đã chạy bị lỗi:
        {code}
        - Traceback / Error:
        {traceback}
        
        Hãy viết lại mã Python để khắc phục lỗi. Lưu kết quả in ra vào stdout.
        """
    else:
        system_content = "Bạn là chuyên gia Data Engineer. Hãy viết mã Python để thực hiện yêu cầu phân tích."
        human_content = f"""
        - Dữ liệu schema: {schema_str}
        - Lịch sử các bước trước: {past_steps}
        - Bước hiện tại cần làm: {current_step}
        
        Hãy viết mã Python. Chỉ dùng các thư viện chuẩn.
        """

    # Gọi chain với 2 biến định sẵn trong PromptTemplate
    response: CoderOutput = llm_coder_chain.invoke(
        {
            "system_prompt": system_content,
            "user_question": human_content
        }
    )

    # Trả về code mới và reset status để executor chạy
    return {
        "code": response.code,
        "execution_status": None,
        "execution_error": None,
        "traceback": None,
        "execution_output": None
    }