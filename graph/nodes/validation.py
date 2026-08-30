from graph.llms import llm
from graph.prompts import validation_prompt
from graph.state import DataAgentState, ValidatorOutput


structured_validation_llm = llm.with_structured_output(ValidatorOutput)
validator_chain = validation_prompt | structured_validation_llm

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
