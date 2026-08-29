from langchain_core.prompts import ChatPromptTemplate
from graph.state import DataAgentState, ValidatorOutput
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_validation_llm = llm.with_structured_output(ValidatorOutput)

validator_prompt = ChatPromptTemplate.from_messages([
    ("system", "Bạn là QA. Đánh giá xem câu trả lời đã thỏa mãn trọn vẹn câu hỏi gốc của user chưa. "
               "Kiểm tra kỹ xem user có yêu cầu vẽ biểu đồ mà câu trả lời lại thiếu ảnh nhúng không."),
    ("human", "Câu hỏi gốc: {user_question}\n\nCâu trả lời đã tạo: {final_answer}")
])

validator_chain = validator_prompt | structured_validation_llm

def validate_node(state: DataAgentState):
    user_question = next((m.content for m in reversed(state["messages"]) if m.type == "human"), "")
    final_answer = state.get("final_answer", "")
    
    result: ValidatorOutput = validator_chain.invoke({
        "user_question": user_question,
        "final_answer": final_answer
    })

    return {
        "is_sufficient": result.is_valid,
        "validation_feedback": result.feedback if not result.is_valid else None
    }