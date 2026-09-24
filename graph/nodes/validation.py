from graph.llms import llm
from graph.prompts import validation_prompt
from graph.state import DataAgentState, ValidatorOutput
from graph.utils import answer_context, artifact_reference_issue, evidence_gap, latest_user_question

validation_chain = validation_prompt | llm.with_structured_output(ValidatorOutput)


def validate_node(state: DataAgentState):
    context = answer_context(state)
    result = validation_chain.invoke({
        **context,
        "final_answer": state.get("final_answer", ""),
    })
    decision, feedback = result.decision, result.feedback
    gap = evidence_gap(state, context)
    issue = artifact_reference_issue(state.get("final_answer", ""), context["artifacts"])
    if gap:
        decision, feedback = "reanalyze", gap
    elif issue:
        decision, feedback = ("revise_answer" if context["artifacts"] else "reanalyze"), issue
    update = {
        "is_sufficient": decision == "accept",
        "validation_decision": decision,
        "validation_feedback": feedback or None,
    }
    if decision == "accept":
        update["answer_history"] = state.get("answer_history", []) + [{
            "question": latest_user_question(state.get("messages", [])),
            "answer": state.get("final_answer", ""),
        }]
    return update
