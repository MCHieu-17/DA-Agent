from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import RouteDecision

llm =  ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_llm = llm.with_structured_output(RouteDecision)

router_system_prompt = """Bạn là hệ thống định tuyến (Router) cho một AI phân tích dữ liệu.
Nhiệm vụ của bạn là đọc câu hỏi và phân loại vào đúng 1 trong 3 nhãn sau:

1. 'chat': Giao tiếp thông thường, hoặc hỏi đáp kiến thức chung không yêu cầu truy vấn/phân tích dữ liệu thực tế.
2. 'analysis': Yêu cầu phân tích dữ liệu ĐÃ ĐẦY ĐỦ VÀ RÕ RÀNG. Câu hỏi có đủ ngữ cảnh (mục tiêu, đối tượng, khoảng thời gian, bộ lọc) để AI có thể trực tiếp viết SQL/Code phân tích ngay.
3. 'clarify_needed': Yêu cầu phân tích dữ liệu nhưng CÒN MƠ HỒ HOẶC THIẾU THÔNG TIN. Ví dụ: Thiếu khoảng thời gian ("doanh thu dạo này"), không rõ tiêu chí ("sản phẩm tốt nhất" - theo view hay theo sales?), hoặc quá chung chung.

THÔNG TIN LƯỢC ĐỒ DỮ LIỆU (SCHEMA) HIỆN CÓ:
{schema_str}

Hãy đối chiếu câu hỏi với lược đồ trên để xem yêu cầu phân tích có rõ ràng và khả thi không, sau đó phân loại.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", router_system_prompt),
    ("human", "Câu hỏi: \n\n{user_question}")
])

router_chain = prompt | structured_llm