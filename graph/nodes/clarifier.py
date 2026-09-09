from langchain_core.messages import AIMessage

from graph.llms import get_node_llm
from graph.prompts import clarifier_prompt
from graph.state import ClarifyDecision, DataAgentState
from graph.utils import latest_human_message


def clarify_node(state: DataAgentState):
    if state.get("clarification_question"):
        content = state["clarification_question"]
        return {"messages": [AIMessage(content=content)], "final_answer": content,
                "workflow_status": "needs_input", "artifacts": []}
    profile_errors = state.get("profile_errors", [])
    if profile_errors:
        details = "\n".join(f"- {error}" for error in profile_errors)
        content = (
            "Mình chưa thể phân tích vì dữ liệu CSV chưa hợp lệ:\n"
            f"{details}\n\n"
            "Bạn hãy cung cấp lại đường dẫn tới file CSV hợp lệ rồi gửi lại yêu cầu."
        )
        return {
            "messages": [AIMessage(content=content)], "final_answer": content,
            "workflow_status": "needs_input",
        }

    try:
        decision: ClarifyDecision = (clarifier_prompt | get_node_llm("clarify").with_structured_output(ClarifyDecision)).invoke(
            {
                "user_question": latest_human_message(state["messages"]),
                "data_schema": state.get("profile_summary", "{}")
            }
        )
        content = f"{decision.reason}\n\n{decision.clarifying_question}"
    except Exception:
        content = (
            "Mình chưa xác định chắc chắn yêu cầu phân tích. "
            "Bạn có thể nêu rõ chỉ số, nhóm dữ liệu và dạng kết quả mong muốn không?"
        )

    return {
        "messages": [AIMessage(content=content)], "final_answer": content,
        "workflow_status": "needs_input",
    }
