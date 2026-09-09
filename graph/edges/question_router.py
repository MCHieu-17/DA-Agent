from graph.state import DataAgentState, RouteDecision
from graph.llms import get_node_llm
from graph.prompts import router_prompt
from graph.utils import format_history, latest_human_message

def question_router(state: DataAgentState):
    messages = state["messages"]
    try:
        decision: RouteDecision = (router_prompt | get_node_llm("router").with_structured_output(RouteDecision)).invoke(
            {
                "history": format_history(messages, exclude_last=True),
                "current_question": latest_human_message(messages),
                "profile_summary": state.get("profile_summary", ""),
            }
        )
    except Exception:
        # A routing/model failure must not accidentally execute generated code.
        return "clarify"

    if decision.intent != "chat" and not state.get("profile_valid", False):
        return "clarify"

    # Ánh xạ intent -> đúng key của path map trong graph.py
    return {"analysis": "analysis", "clarify_needed": "clarify", "chat": "chat"}[decision.intent]
