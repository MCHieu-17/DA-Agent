from langchain_core.messages import AIMessage

from graph.state import DataAgentState, ClarifyDecision
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_clarify_llm = llm.with_structured_output(ClarifyDecision)

clarify_system_prompt = """Bạn là trợ lý AI chuyên làm rõ yêu cầu phân tích dữ liệu.
Hệ thống đã xác định câu hỏi dưới đây của người dùng CÒN THIẾU THÔNG TIN để có thể truy vấn/phân tích dữ liệu.

NHIỆM VỤ CỦA BẠN:
1. So sánh câu hỏi với Schema dữ liệu hiện có để tìm ra điểm bị khuyết (ví dụ: thiếu điều kiện thời gian, chưa rõ metric đo lường, chưa xác định bảng/cột cần dùng).
2. Viết 1 câu duy nhất nêu rõ lý do chưa thể phân tích.
3. Đặt 1 câu hỏi ngắn gọn để yêu cầu người dùng bổ sung, luôn đưa ra 2-3 gợi ý (options) có sẵn trong Schema để họ dễ chọn.

Văn phong ngắn gọn, thân thiện và đi thẳng vào vấn đề."""

prompt = ChatPromptTemplate.from_messages([
    ("system", clarify_system_prompt),
    ("human", """Schema / Danh sách bảng & cột hiện có:
{data_schema}

Câu hỏi của người dùng:
{user_question}"""),
])

clarify_chain = prompt | structured_clarify_llm

def clarify_node(state: DataAgentState):
    decision: ClarifyDecision = clarify_chain.invoke(
        {
            "user_question": state["messages"][-1].content,
            "data_schema": state["schema_str"]
        }
    )
    return {
        "messages": [AIMessage(content=decision.clarifying_question)],
    }