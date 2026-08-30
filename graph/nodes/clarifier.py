from langchain_core.messages import AIMessage

from graph.llms import llm
from graph.prompts import clarifier_prompt
from graph.state import ClarifyDecision, DataAgentState


structured_clarify_llm = llm.with_structured_output(ClarifyDecision)
clarify_chain = clarifier_prompt | structured_clarify_llm

def clarify_node(state: DataAgentState):
    decision: ClarifyDecision = clarify_chain.invoke(
        {
            "user_question": state["messages"][-1].content,
            "data_schema": state["schema_str"]
        }
    )
    return {
        "messages": [AIMessage(content=decision.clarifying_question)],
    }
