from graph.llms import get_node_llm
from graph.prompts import (
    ERROR_CONTEXT_TEMPLATE,
    initial_planner_prompt,
    replan_prompt,
)
from graph.state import AnalysisPlan, DataAgentState
from graph.utils import format_history, format_step_evidence, latest_human_message

structured_planner_llm = get_node_llm("planner").with_structured_output(AnalysisPlan)

initial_planner_chain = initial_planner_prompt | structured_planner_llm
replan_chain = replan_prompt | structured_planner_llm

def planner_node(state: DataAgentState):
    messages = state["messages"]
    current_question = latest_human_message(messages)                  # câu hỏi user gần nhất
    history = format_history(messages, exclude_last=True)  # ngữ cảnh các lượt trước

    schema_str = state.get("schema_str", "")
    past_steps = format_step_evidence(state.get("past_steps", []))
    current_plan = state.get("plan", [])

    execution_status = state.get("execution_status")
    replan_count = state.get("replan_count", 0)

    execution_replan = execution_status == "error"
    validation_replan = (
        state.get("is_sufficient") is False
        and bool(state.get("validation_feedback"))
    )
    is_replan = execution_replan or validation_replan

    replan_context = ""
    replan_reason = None
    if execution_replan:
        replan_reason = "execution"
        replan_context = ERROR_CONTEXT_TEMPLATE.format(
            execution_error=state.get("execution_error"),
            traceback=state.get("traceback"),
            debug_feedback=state.get("debug_feedback"),
        )
    elif validation_replan:
        replan_reason = "validation"
        replan_context = (
            "LƯU Ý: Câu trả lời trước chưa đạt kiểm tra chất lượng.\n"
            f"- Feedback: {state.get('validation_feedback')}\n"
            f"- Bản trả lời trước: {state.get('final_answer')}"
        )

    if is_replan:
        replan_count += 1

    if is_replan:
        chain = replan_chain
        prompt_input = {
            "history": history,
            "current_question": current_question,
            "schema_str": schema_str,
            "current_plan": current_plan,
            "past_steps": past_steps,
            "replan_context": replan_context,
        }
    else:
        chain = initial_planner_chain
        prompt_input = {
            "history": history,
            "current_question": current_question,
            "schema_str": schema_str,
        }

    try:
        result: AnalysisPlan = chain.invoke(prompt_input)
    except Exception as exc:
        return {
            "node_error": f"PlannerError: {type(exc).__name__}: {exc}",
            "workflow_status": "failed",
        }

    # Cập nhật và "dọn dẹp" state để chạy luồng mới
    return {
        "plan": result.steps,
        "current_step_idx": 0,     # Reset chỉ mục
        "retry_count": 0,          # Reset retry
        "replan_count": replan_count,
        "replan_reason": replan_reason,
        "execution_status": None,  # Reset status
        "execution_output": None,
        "execution_error": None,
        "traceback": None,
        "code": None,
        "debug_feedback": None,
        "is_sufficient": None,
        "validation_feedback": None,
        "final_answer": None,
        "workflow_status": "running",
        "node_error": None,
    }
