from graph.llms import llm
from graph.prompts import (
    ERROR_CONTEXT_TEMPLATE,
    initial_planner_prompt,
    replan_prompt,
)
from graph.state import AnalysisPlan, DataAgentState
from graph.utils import format_history

structured_planner_llm = llm.with_structured_output(AnalysisPlan)

initial_planner_chain = initial_planner_prompt | structured_planner_llm
replan_chain = replan_prompt | structured_planner_llm

def planner_node(state: DataAgentState):
    messages = state["messages"]
    current_question = messages[-1].content                            # câu hỏi lượt này
    history = format_history(messages, max_msgs=6, exclude_last=True)  # ngữ cảnh các lượt trước

    schema_str = state.get("schema_str", "")
    past_steps = state.get("past_steps", [])
    current_plan = state.get("plan", [])

    execution_status = state.get("execution_status")
    replan_count = state.get("replan_count", 0)

    # Nếu replan vì quá trình chạy trước đó bị lỗi nhiều lần
    error_context = ""
    if execution_status == "error":
        error_context = ERROR_CONTEXT_TEMPLATE.format(
            execution_error=state.get("execution_error")
        )
        replan_count += 1  # Tăng số lần replan

    if len(past_steps) > 0 or execution_status == "error":
        chain = replan_chain
        prompt_input = {
            "history": history,
            "current_question": current_question,
            "schema_str": schema_str,
            "current_plan": current_plan,
            "past_steps": past_steps,
            "error_context": error_context,
        }
    else:
        chain = initial_planner_chain
        prompt_input = {
            "history": history,
            "current_question": current_question,
            "schema_str": schema_str,
        }

    result: AnalysisPlan = chain.invoke(prompt_input)

    # Cập nhật và "dọn dẹp" state để chạy luồng mới
    return {
        "plan": result.steps,
        "current_step_idx": 0,     # Reset chỉ mục
        "retry_count": 0,          # Reset retry
        "replan_count": replan_count,
        "execution_status": None,  # Reset status
        "code": None,
        "debug_feedback": None
    }
