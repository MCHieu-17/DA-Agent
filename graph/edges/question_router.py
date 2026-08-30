from graph.state import DataAgentState, RouteDecision
from langchain_core.prompts import ChatPromptTemplate
from graph.llms import llm
from graph.utils import format_history

structured_router_llm = llm.with_structured_output(RouteDecision)

system_prompt = """Bạn là hệ thống định tuyến (Router) cho một AI phân tích dữ liệu.
Nhiệm vụ của bạn là đọc câu hỏi và phân loại vào đúng 1 trong 3 nhãn sau:

1. 'chat': Giao tiếp thông thường, hoặc hỏi đáp kiến thức chung không yêu cầu truy vấn/phân tích dữ liệu thực tế.
2. 'analysis': Yêu cầu phân tích dữ liệu ĐÃ ĐẦY ĐỦ VÀ RÕ RÀNG. Câu hỏi có đủ ngữ cảnh (mục tiêu, đối tượng, khoảng thời gian, bộ lọc) để AI có thể trực tiếp viết SQL/Code phân tích ngay.
3. 'clarify_needed': Yêu cầu phân tích dữ liệu nhưng CÒN MƠ HỒ HOẶC THIẾU THÔNG TIN. Ví dụ: Thiếu khoảng thời gian ("doanh thu dạo này"), không rõ tiêu chí ("sản phẩm tốt nhất" - theo view hay theo sales?), hoặc quá chung chung.

QUY TẮC NGỮ CẢNH: Câu hiện tại có thể là câu nối tiếp (vd: "thế còn theo quý?", "vẽ lại thành biểu đồ tròn").
PHẢI đọc lịch sử hội thoại để suy ra ý đầy đủ trước khi phân loại.
Câu nối tiếp mà ngữ cảnh trong lịch sử đã đủ rõ thì phân loại 'analysis'.

THÔNG TIN LƯỢC ĐỒ DỮ LIỆU (SCHEMA) HIỆN CÓ:
{schema_str}

Hãy đối chiếu câu hỏi với lược đồ trên để xem yêu cầu phân tích có rõ ràng và khả thi không, sau đó phân loại.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "Lịch sử hội thoại:\n{history}\n\nCâu hiện tại:\n\n{current_question}")
])

router_chain = prompt | structured_router_llm

def question_router(state: DataAgentState):
    messages = state["messages"]
    decision: RouteDecision = router_chain.invoke(
        {
            "history": format_history(messages, max_msgs=6, exclude_last=True),
            "current_question": messages[-1].content,
            "schema_str": state.get("schema_str", ""),
        }
    )
    # Ánh xạ intent -> đúng key của path map trong graph.py
    return {"analysis": "analysis", "clarify_needed": "clarify", "chat": "chat"}[decision.intent]
