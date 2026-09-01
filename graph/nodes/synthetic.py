from graph.llms import get_node_llm
from graph.prompts import synthetic_prompt
from graph.state import DataAgentState, SyntheticOutput
from graph.utils import format_step_evidence, latest_human_message


structured_synthetic_llm = get_node_llm("synthetic").with_structured_output(
    SyntheticOutput
)
synthetic_chain = synthetic_prompt | structured_synthetic_llm


def synthetic_node(state: DataAgentState):
    # Lấy câu hỏi gốc của user (tìm message Human đầu tiên hoặc gần nhất)
    user_question = latest_human_message(state["messages"])

    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])
    artifacts = state.get("artifacts", [])

    steps_text = format_step_evidence(past_steps)

    try:
        result: SyntheticOutput = synthetic_chain.invoke({
            "user_question": user_question,
            "plan": plan,
            "past_steps": steps_text,
            "artifacts": artifacts
        })
    except Exception as exc:
        return {
            "node_error": f"SyntheticError: {type(exc).__name__}: {exc}",
            "workflow_status": "failed",
        }

    return {
        "final_answer": result.final_answer,
        "node_error": None,
    }
