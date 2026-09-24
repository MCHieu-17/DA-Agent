from graph.llms import llm
from graph.prompts import action_prompt
from graph.state import ActionDecision, DataAgentState
from graph.tools import TOOL_CATALOG
from graph.utils import latest_user_question

selector_chain = action_prompt | llm.with_structured_output(ActionDecision)


def action_selector_node(state: DataAgentState):
    index = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    if index >= len(plan):
        return {"action": {"mode": "done"}}
    step = plan[index]
    decision = selector_chain.invoke({
        "user_question": latest_user_question(state["messages"]),
        "tool_catalog": TOOL_CATALOG,
        "profile_summary": state.get("profile_summary", ""),
        "step": step,
        "past_steps": state.get("past_steps", [])[-5:],
    })
    return {"action": decision.model_dump()}
