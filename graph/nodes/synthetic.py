from graph.llms import llm
from graph.prompts import synthetic_prompt
from graph.state import DataAgentState, SyntheticOutput
from graph.utils import answer_context, resolve_artifact_tokens

synthetic_chain = synthetic_prompt | llm.with_structured_output(SyntheticOutput)


def synthetic_node(state: DataAgentState):
    prior_answer = state.get("final_answer") or ""
    context = answer_context(state)
    result = synthetic_chain.invoke({
        **context,
        "prior_answer": prior_answer,
        "validation_feedback": state.get("validation_feedback") or "",
    })
    return {
        "final_answer": resolve_artifact_tokens(result.final_answer, context["artifacts"]),
        "synthesis_retry_count": state.get("synthesis_retry_count", 0) + int(bool(prior_answer)),
    }
