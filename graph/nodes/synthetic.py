from langchain_core.prompts import ChatPromptTemplate
from graph.state import SyntheticOutput, DataAgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_synthetic_llm = llm.with_structured_output(SyntheticOutput)

synthetic_prompt = ChatPromptTemplate.from_messages([
    ("system", "Bạn là chuyên gia phân tích dữ liệu. Hãy tổng hợp kết quả để trả lời user. "
               "Dùng Markdown cho đẹp. Các file trong 'artifacts' đã chứa sẵn đường dẫn, hãy nhúng ảnh bằng cú pháp: ![Mô tả](đường_dẫn)."),
    ("human", "Câu hỏi: {user_question}\n\nKế hoạch: {plan}\n\n"
              "Lịch sử thực hiện:\n{past_steps}\n\nDanh sách Artifacts: {artifacts}")
])
synthetic_chain = synthetic_prompt | structured_synthetic_llm


def synthetic_node(state: DataAgentState):
    # Lấy câu hỏi gốc của user (tìm message Human đầu tiên hoặc gần nhất)
    user_question = next((m.content for m in reversed(state["messages"]) if m.type == "human"), "")
    
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])
    artifacts = state.get("artifacts", [])
    
    # Format lịch sử bước cho dễ đọc
    steps_text = "\n".join([
        f"- Bước: {s['step']}\n  Kết quả (stdout): {s['stdout']}\n  Files: {s.get('artifacts', [])}" 
        for s in past_steps
    ])

    result: SyntheticOutput = synthetic_chain.invoke({
        "user_question": user_question,
        "plan": plan,
        "past_steps": steps_text,
        "artifacts": artifacts
    })

    return {
        "final_answer": result.final_answer,
        # Lưu vào messages để UI/Frontend có thể render markdown
        "messages": [AIMessage(content=result.final_answer)] 
    }