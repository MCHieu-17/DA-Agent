
from graph.state import DataAgentState
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

system_prompt = "Bạn là chuyên gia Debug. Hãy phân tích đoạn code bị lỗi và traceback, giải thích nguyên nhân ngắn gọn và đưa ra hướng dẫn từng bước để sửa lỗi."

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{human_message}")
])

debug_chain = prompt | llm
def debug_node(state: DataAgentState):    
    human_content = f"""
    - Đoạn code bị lỗi:
    {state.get('code')}
    
    - Lỗi (Exception): {state.get('execution_error')}
    - Traceback: 
    {state.get('traceback')}
    """
    
    response = debug_chain.invoke(
        {"human_message": human_content}
    )
    
    return {
        "debug_feedback": response.content,
    }