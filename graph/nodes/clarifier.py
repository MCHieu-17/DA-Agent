from langchain_core.messages import AIMessage

from graph.llms import get_node_llm
from graph.prompts import clarifier_prompt
from graph.state import ClarifyDecision, DataAgentState
from graph.utils import latest_human_message


structured_clarify_llm = get_node_llm("clarify").with_structured_output(
    ClarifyDecision
)
clarify_chain = clarifier_prompt | structured_clarify_llm

def clarify_node(state: DataAgentState):
    schema_errors = state.get("schema_errors", [])
    if schema_errors:
        details = "\n".join(f"- {error}" for error in schema_errors)
        content = (
            "Mình chưa thể phân tích vì dữ liệu CSV chưa hợp lệ:\n"
            f"{details}\n\n"
            "Bạn hãy cung cấp lại đường dẫn tới file CSV hợp lệ rồi gửi lại yêu cầu."
        )
        return {
            "messages": [AIMessage(content=content)],
            "workflow_status": "needs_input",
        }

    try:
        decision: ClarifyDecision = clarify_chain.invoke(
            {
                "user_question": latest_human_message(state["messages"]),
                "data_schema": state["schema_str"]
            }
        )
        content = f"{decision.reason}\n\n{decision.clarifying_question}"
    except Exception:
        content = (
            "Mình chưa xác định chắc chắn yêu cầu phân tích. "
            "Bạn có thể nêu rõ chỉ số, nhóm dữ liệu và dạng kết quả mong muốn không?"
        )

    return {
        "messages": [AIMessage(content=content)],
        "workflow_status": "needs_input",
    }
