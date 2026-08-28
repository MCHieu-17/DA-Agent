from langchain_core.messages import AIMessage

from graph.state import DataAgentState, ClarifyDecision
from graph.chains import llm_clarify_chain


def clarify_node(state: DataAgentState):
    decision: ClarifyDecision = llm_clarify_chain.invoke(
        {
            "user_question": state["messages"][-1].content,
            "data_schema": state["schema_str"]
        }
    )
    return {
        "messages": [AIMessage(content=decision.clarifying_question)],
    }