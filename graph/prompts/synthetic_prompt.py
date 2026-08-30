from langchain_core.prompts import ChatPromptTemplate


SYNTHETIC_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích dữ liệu. Hãy tổng hợp kết quả để trả lời user. Dùng Markdown cho đẹp. Các file trong 'artifacts' đã chứa sẵn đường dẫn, hãy nhúng ảnh bằng cú pháp: ![Mô tả](đường_dẫn)."""


synthetic_prompt = ChatPromptTemplate.from_messages([
    ("system", SYNTHETIC_SYSTEM_PROMPT),
    ("human", """Câu hỏi: {user_question}

Kế hoạch: {plan}

Lịch sử thực hiện:
{past_steps}

Danh sách Artifacts: {artifacts}"""),
])
