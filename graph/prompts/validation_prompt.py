from langchain_core.prompts import ChatPromptTemplate


VALIDATION_SYSTEM_PROMPT = """Bạn là QA cho hệ thống phân tích dữ liệu.
Chỉ chấp nhận câu trả lời khi:
1. Trả lời đúng và đủ câu hỏi user.
2. Các số liệu/nhận định có căn cứ trong kết quả execute, không tự suy diễn.
3. Nếu user yêu cầu biểu đồ thì artifact phải tồn tại trong danh sách và được nhúng.
Nếu bằng chứng execute chưa đủ, phải trả về is_valid=False và feedback cụ thể."""


validation_prompt = ChatPromptTemplate.from_messages([
    ("system", VALIDATION_SYSTEM_PROMPT),
    ("human", """Câu hỏi gốc: {user_question}

Câu trả lời đã tạo: {final_answer}

Schema dữ liệu: {schema_str}

Kết quả execute: {past_steps}

Artifacts thực tế: {artifacts}"""),
])
