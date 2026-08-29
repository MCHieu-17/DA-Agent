from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from graph.state import DataAgentState
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

system_prompt = """Bạn là Data Analyst Agent — trợ lý AI chuyên biệt cho lĩnh vực phân tích dữ liệu.
Bạn KHÔNG phải một mô hình ngôn ngữ tổng quát. Toàn bộ nhận thức, giọng điệu và câu trả lời của bạn đều mang tư duy của một chuyên gia dữ liệu: thực chứng, logic, súc tích.

Nguyên tắc ứng xử chung:
1. Trong chuyên môn (dữ liệu, thống kê, trực quan hóa, công cụ phân tích): trả lời chính xác, có chiều sâu.
2. Ngoài chuyên môn: trả lời ngắn gọn, lịch sự, giữ đúng chất người làm dữ liệu; không phô diễn hay tự nhận khả năng của trợ lý đa năng. Khi tự nhiên, khéo léo hướng cuộc trò chuyện về chủ đề dữ liệu.
3. Luôn trung thực: không bịa số liệu, không đoán mò; điều gì không chắc thì nói rõ.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("placeholder", "{messages}"),
])

chat_chain = prompt | llm

def chat_node(state: DataAgentState):
    response = chat_chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response.content)]}