from langchain_core.prompts import ChatPromptTemplate

from configuration import PLAN_MAX_STEPS


INITIAL_PLANNER_SYSTEM_PROMPT = f"""Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch thực thi. KHÔNG VIẾT CODE.

Mỗi bước sẽ chạy trong một Python process độc lập và phải đọc lại CSV. Vì vậy:
- Mặc định trả về ĐÚNG 1 bước hoàn chỉnh, gộp đọc dữ liệu, tính toán, trực quan hóa và print kết quả cần thiết.
- Chỉ tách 2-{PLAN_MAX_STEPS} bước khi yêu cầu thực sự có các phần độc lập không thể xử lý rõ ràng trong một chương trình.
- Không tạo bước riêng chỉ để đọc file, kiểm tra schema, tính từng KPI hoặc in kết quả.
- Không vượt quá {PLAN_MAX_STEPS} bước."""

REPLAN_SYSTEM_PROMPT = f"""Bạn là chuyên gia dữ liệu. Hãy lập kế hoạch TIẾP THEO hoặc ĐIỀU CHỈNH KẾ HOẠCH nếu có lỗi. KHÔNG VIẾT CODE.
Chỉ lập các bước còn thiếu, mặc định gộp thành 1 bước hoàn chỉnh và không vượt quá {PLAN_MAX_STEPS} bước."""

ERROR_CONTEXT_TEMPLATE = """LƯU Ý: Bước hiện tại tiếp tục lỗi sau các lần debug. Hãy tìm HƯỚNG TIẾP CẬN KHÁC để thay thế.
- Loại lỗi: {execution_error}
- Traceback gần nhất: {traceback}
- Phân tích của debugger: {debug_feedback}"""


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
{replan_context}

Chỉ đưa ra các bước tiếp theo cần làm; không lặp lại bước đã thành công."""),
])
