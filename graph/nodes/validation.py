from graph.llms import llm
from graph.prompts import validation_prompt
from graph.state import DataAgentState, ValidatorOutput
from graph.utils import latest_user_question

validation_chain = validation_prompt | llm.with_structured_output(ValidatorOutput)


def validate_node(state: DataAgentState):
    result = validation_chain.invoke({"user_question": latest_user_question(state["messages"]), "evidence": state.get("past_steps", [])[-12:], "final_answer": state.get("final_answer", "")})
    return {"is_sufficient": result.is_valid, "validation_feedback": result.feedback if not result.is_valid else None}
