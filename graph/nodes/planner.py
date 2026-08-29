from graph.state import DataAgentState, AnalysisPlan
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.utils import format_history

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_planner_llm = llm.with_structured_output(AnalysisPlan)

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    ("human", "{human_prompt}")
])

planner_chain = prompt | structured_planner_llm

def planner_node(state: DataAgentState):
    messages = state["messages"]
    current_question = messages[-1].content                            # câu hỏi lượt này
    history = format_history(messages, max_msgs=6, exclude_last=True)  # ngữ cảnh các lượt trước

    schema_str = state.get("schema_str", "")
    past_steps = state.get("past_steps", [])
    current_plan = state.get("plan", [])

    execution_status = state.get("execution_status")
    replan_count = state.get("replan_count", 0)

    # Nếu replan vì quá trình chạy trước đó bị lỗi nhiều lần
    error_context = ""
    if execution_status == "error":
        error_context = f"\nLƯU Ý: Bước hiện tại bị lỗi '{state.get('execution_error')}'. Hãy tìm HƯỚNG TIẾP CẬN KHÁC để thay thế."
        replan_count += 1  # Tăng số lần replan

    if len(past_steps) > 0 or execution_status == "error":
        system_prompt = "Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch TIẾP THEO hoặc ĐIỀU CHỈNH KẾ HOẠCH nếu có lỗi. KHÔNG VIẾT CODE."
        human_prompt = f"""
        - Lịch sử hội thoại:
        {history}
        - Câu hỏi hiện tại: {current_question}
        - Lược đồ: {schema_str}
        - Kế hoạch cũ: {current_plan}
        - Đã thực hiện thành công: {past_steps}{error_context}

        Hãy đưa ra các bước cần làm.
        """
    else:
        system_prompt = "Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch từng bước logic. KHÔNG VIẾT CODE."
        human_prompt = f"""
        - Lịch sử hội thoại:
        {history}
        - Câu hỏi hiện tại: {current_question}
        - Lược đồ: {schema_str}
        """

    result: AnalysisPlan = planner_chain.invoke({
        "system_prompt": system_prompt,
        "human_prompt": human_prompt
    })

    # Cập nhật và "dọn dẹp" state để chạy luồng mới
    return {
        "plan": result.steps,
        "current_step_idx": 0,     # Reset chỉ mục
        "retry_count": 0,          # Reset retry
        "replan_count": replan_count,
        "execution_status": None,  # Reset status
        "code": None,
        "debug_feedback": None
    }