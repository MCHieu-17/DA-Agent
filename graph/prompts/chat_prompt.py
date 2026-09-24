from langchain_core.prompts import ChatPromptTemplate


CHAT_SYSTEM_PROMPT = """Trả lời bằng ngôn ngữ của người dùng, tự nhiên và súc tích.
Với câu hỏi về dữ liệu, thống kê hoặc trực quan hóa, giải thích chính xác và nêu giới hạn khi cần. Không tự tạo số liệu hay nói đã phân tích tệp nếu chưa có evidence. Với câu hỏi thông thường, trả lời trực tiếp và lịch sự."""


chat_prompt = ChatPromptTemplate.from_messages([
    ("system", CHAT_SYSTEM_PROMPT),
    ("human", "Lịch sử hỏi đáp đã chấp nhận:\n{conversation_history}\n\nYêu cầu hiện tại:\n{user_question}"),
])
