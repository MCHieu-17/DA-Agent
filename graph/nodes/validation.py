from langchain_core.messages import AIMessage

from graph.llms import get_node_llm
from graph.prompts import validation_prompt
from graph.state import DataAgentState, ValidatorOutput
from graph.utils import format_step_evidence, latest_human_message


structured_validation_llm = get_node_llm("validator").with_structured_output(
    ValidatorOutput
)
validator_chain = validation_prompt | structured_validation_llm

def validate_node(state: DataAgentState):
    user_question = latest_human_message(state["messages"])
    final_answer = state.get("final_answer", "")

    try:
        result: ValidatorOutput = validator_chain.invoke({
            "user_question": user_question,
            "final_answer": final_answer,
            "schema_str": state.get("schema_str", ""),
            "past_steps": format_step_evidence(state.get("past_steps", [])),
            "artifacts": state.get("artifacts", []),
        })
    except Exception as exc:
        return {
            "is_sufficient": False,
            "validation_feedback": "Validator không chạy được.",
            "node_error": f"ValidatorError: {type(exc).__name__}: {exc}",
            "workflow_status": "failed",
        }

    update: dict = {
        "is_sufficient": result.is_valid,
        "validation_feedback": result.feedback if not result.is_valid else None,
        "workflow_status": "success" if result.is_valid else "running",
        "node_error": None,
    }
    if result.is_valid:
        update["messages"] = [AIMessage(content=final_answer)]
    return update
