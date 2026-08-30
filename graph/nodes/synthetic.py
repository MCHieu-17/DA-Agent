from langchain_core.messages import AIMessage

from graph.llms import llm
from graph.prompts import synthetic_prompt
from graph.state import DataAgentState, SyntheticOutput


structured_synthetic_llm = llm.with_structured_output(SyntheticOutput)
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
