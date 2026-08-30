from langchain_core.prompts import ChatPromptTemplate


INITIAL_PLANNER_SYSTEM_PROMPT = """Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch từng bước logic. KHÔNG VIẾT CODE."""

REPLAN_SYSTEM_PROMPT = """Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch TIẾP THEO hoặc ĐIỀU CHỈNH KẾ HOẠCH nếu có lỗi. KHÔNG VIẾT CODE."""

ERROR_CONTEXT_TEMPLATE = """LƯU Ý: Bước hiện tại bị lỗi '{execution_error}'. Hãy tìm HƯỚNG TIẾP CẬN KHÁC để thay thế."""


initial_planner_prompt = ChatPromptTemplate.from_messages([
    ("system", INITIAL_PLANNER_SYSTEM_PROMPT),
    ("human", """- Lịch sử hội thoại:
{history}
- Câu hỏi hiện tại: {current_question}
- Lược đồ: {schema_str}"""),
])

replan_prompt = ChatPromptTemplate.from_messages([
    ("system", REPLAN_SYSTEM_PROMPT),
    ("human", """- Lịch sử hội thoại:
{history}
- Câu hỏi hiện tại: {current_question}
- Lược đồ: {schema_str}
- Kế hoạch cũ: {current_plan}
- Đã thực hiện thành công: {past_steps}
{error_context}

Hãy đưa ra các bước cần làm."""),
])
