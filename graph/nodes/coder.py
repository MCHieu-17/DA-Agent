from graph.state import DataAgentState, CoderOutput
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_coder_llm = llm.with_structured_output(CoderOutput)


prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_question}")
    ])

coder_chain = prompt | structured_coder_llm


def coder_node(state: DataAgentState):
    plan = state.get("plan", [])
    current_idx = state.get("current_step_idx", 0)
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    
    schema_str = state.get("schema_str", "")
    past_steps = state.get("past_steps", [])
    code = state.get("code", "")
    traceback = state.get("traceback", "")
    ARTIFACTS_DIR = state.get("artifacts_dir")

    # Quy tắc chung về môi trường headless + nơi lưu file
    headless_rule = (
        f"MÔI TRƯỜNG HEADLESS (không có GUI). Nếu vẽ biểu đồ: "
        f"TUYỆT ĐỐI KHÔNG dùng plt.show() hay fig.show(). "
        f"Hãy lưu file vào thư mục '{ARTIFACTS_DIR}' (thư mục này đã tồn tại sẵn), ví dụ: "
        f"plt.savefig('{ARTIFACTS_DIR}/chart.png') hoặc fig.write_html('{ARTIFACTS_DIR}/chart.html'). "
        f"Sau đó print ra đường dẫn file đã lưu."
    )

    # Phân nhánh logic bằng f-string để tự động điền dữ liệu từ state
    if state.get("execution_status") == "error":
        system_content = f"Bạn là chuyên gia Data Engineer. SỬA LỖI mã Python. {headless_rule}"
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
        system_content = f"Bạn là chuyên gia Data Engineer. Viết mã Python. {headless_rule}"
        human_content = f"""
        - Dữ liệu schema: {schema_str}
        - Lịch sử các bước trước: {past_steps}
        - Bước hiện tại cần làm: {current_step}
        
        Hãy viết mã Python. Chỉ dùng các thư viện phổ biến cho phân tích dữ liệu 
        (pandas, numpy, matplotlib, plotly...). Không tự ý tạo lại thư mục '{ARTIFACTS_DIR}'.
        """

    # Gọi chain với 2 biến định sẵn trong PromptTemplate
    response: CoderOutput = coder_chain.invoke(
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