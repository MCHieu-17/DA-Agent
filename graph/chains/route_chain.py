from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import RouteDecision

llm =  ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_llm = llm.with_structured_output(RouteDecision)

system_prompt = "Phân loại câu hỏi của người dùng vào đúng 1 nhãn: chat, analysis, clarify_needed."
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{user_question}")
])