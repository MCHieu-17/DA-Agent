from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

system_prompt = "Bạn là chuyên gia Debug. Hãy phân tích đoạn code bị lỗi và traceback, giải thích nguyên nhân ngắn gọn và đưa ra hướng dẫn từng bước để sửa lỗi."

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{human_message}")
])

debug_chain = prompt | llm