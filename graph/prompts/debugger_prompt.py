from langchain_core.prompts import ChatPromptTemplate


DEBUGGER_SYSTEM_PROMPT = """Bạn là chuyên gia Debug. Hãy phân tích đoạn code bị lỗi và traceback, giải thích nguyên nhân ngắn gọn và đưa ra hướng dẫn từng bước để sửa lỗi."""


debugger_prompt = ChatPromptTemplate.from_messages([
    ("system", DEBUGGER_SYSTEM_PROMPT),
    ("human", """- Đoạn code bị lỗi:
{code}

- Lỗi (Exception): {execution_error}
- Traceback:
{traceback}"""),
])
