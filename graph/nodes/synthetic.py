from langchain_core.messages import AIMessage

from graph.llms import llm
from graph.prompts import synthetic_prompt
from graph.state import DataAgentState, SyntheticOutput
from graph.utils import latest_user_question

synthetic_chain = synthetic_prompt | llm.with_structured_output(SyntheticOutput)


def synthetic_node(state: DataAgentState):
    result = synthetic_chain.invoke({"user_question": latest_user_question(state["messages"]), "assumptions": state.get("assumptions", []), "past_steps": state.get("past_steps", [])[-12:], "artifacts": state.get("artifacts", [])})
    return {"final_answer": result.final_answer, "messages": [AIMessage(content=result.final_answer)]}
