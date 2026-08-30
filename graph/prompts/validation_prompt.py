from langchain_core.prompts import ChatPromptTemplate


VALIDATION_SYSTEM_PROMPT = """Bạn là QA. Đánh giá xem câu trả lời đã thỏa mãn trọn vẹn câu hỏi gốc của user chưa. Kiểm tra kỹ xem user có yêu cầu vẽ biểu đồ mà câu trả lời lại thiếu ảnh nhúng không."""


validation_prompt = ChatPromptTemplate.from_messages([
    ("system", VALIDATION_SYSTEM_PROMPT),
    ("human", """Câu hỏi gốc: {user_question}

Câu trả lời đã tạo: {final_answer}"""),
])
