from graph.llms import llm
from graph.prompts import initial_planner_prompt, replan_prompt
from graph.state import AnalysisPlan, DataAgentState
from graph.utils import format_answer_history, latest_user_question

planner_llm = llm.with_structured_output(AnalysisPlan)
initial_planner_chain = initial_planner_prompt | planner_llm
replan_chain = replan_prompt | planner_llm


def planner_node(state: DataAgentState):
    messages = state["messages"]
    question = latest_user_question(messages)
    history = format_answer_history(state.get("answer_history"))
    is_replan = bool(state.get("past_steps") or state.get("validation_feedback") or state.get("execution_status") == "error")
    if is_replan:
        result = replan_chain.invoke({"history": history, "current_question": question, "schema_str": state.get("profile_summary", ""), "past_steps": state.get("past_steps", [])[-8:], "feedback": state.get("validation_feedback") or state.get("traceback") or state.get("execution_error") or "Refine the plan."})
    else:
        result = initial_planner_chain.invoke({"history": history, "current_question": question, "schema_str": state.get("profile_summary", "")})
    return {"plan": [step.model_dump() for step in result.steps], "assumptions": result.assumptions, "current_step_idx": 0, "retry_count": 0, "tool_retry_count": 0, "replan_count": state.get("replan_count", 0) + int(is_replan), "execution_status": None, "validation_feedback": None, "validation_decision": None, "final_answer": None, "code": None}
