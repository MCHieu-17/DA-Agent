from graph.llms import llm
from graph.e2b_executor import sandbox_file_map
from graph.prompts import error_prompt, normal_prompt
from graph.state import CoderOutput, DataAgentState
from graph.utils import latest_user_question

coder_llm = llm.with_structured_output(CoderOutput)
normal_coder_chain = normal_prompt | coder_llm
error_coder_chain = error_prompt | coder_llm


def coder_node(state: DataAgentState):
    index = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    step = plan[index] if index < len(plan) else {"objective": "Complete the requested analysis."}
    if state.get("execution_status") == "error":
        response = error_coder_chain.invoke({"user_question": latest_user_question(state.get("messages", [])), "current_step": step.get("objective", ""), "success_criteria": step.get("success_criteria", ""), "assumptions": state.get("assumptions", []), "sandbox_file_map": state.get("sandbox_file_map") or sandbox_file_map(state), "code": state.get("code", ""), "traceback": state.get("debug_feedback") or state.get("traceback", "")})
    else:
        response = normal_coder_chain.invoke({
            "user_question": latest_user_question(state["messages"]),
            "current_step": step.get("objective", ""),
            "success_criteria": step.get("success_criteria", ""),
            "fallback_reason": state.get("action", {}).get("fallback_reason") or "",
            "assumptions": state.get("assumptions", []),
            "sandbox_file_map": state.get("sandbox_file_map") or sandbox_file_map(state),
            "past_steps": state.get("past_steps", [])[-5:],
        })
    return {"code": response.code, "execution_status": None, "execution_error": None, "traceback": None, "execution_output": None}
