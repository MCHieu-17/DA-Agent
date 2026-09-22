from graph.llms import llm
from graph.prompts import action_prompt
from graph.state import ActionDecision, DataAgentState
from graph.tools import TOOL_CATALOG

selector_chain = action_prompt | llm.with_structured_output(ActionDecision)


def action_selector_node(state: DataAgentState):
    index = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    if index >= len(plan):
        return {"action": {"mode": "done"}}
    step = plan[index]
    decision = selector_chain.invoke({"tool_catalog": TOOL_CATALOG, "profile_summary": state.get("profile_summary", ""), "step": step, "past_steps": state.get("past_steps", [])[-5:]})
    action = decision.model_dump()
    if step.get("kind") in {"explore", "query", "visualize"} and action["mode"] == "code":
        action = {"mode": "tool", "tool_name": {"explore": "describe_table", "query": "run_query", "visualize": "create_chart"}[step["kind"]], "arguments": {}, "fallback_reason": None}
    return {"action": action}
