from graph.llms import llm
from graph.prompts import error_prompt, normal_prompt
from graph.state import CoderOutput, DataAgentState


structured_coder_llm = llm.with_structured_output(CoderOutput)
normal_coder_chain = normal_prompt | structured_coder_llm
error_coder_chain = error_prompt | structured_coder_llm


def coder_node(state: DataAgentState):
    plan = state.get("plan", [])
    current_idx = state.get("current_step_idx", 0)
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    
    schema_str = state.get("schema_str", "")
    past_steps = state.get("past_steps", [])
    code = state.get("code", "")
    traceback = state.get("traceback", "")
    artifacts_dir = state.get("artifacts_dir") or "artifacts"

    prompt_input = {
        "schema_str": schema_str,
        "past_steps": past_steps,
        "current_step": current_step,
        "artifacts_dir": artifacts_dir,
    }

    if state.get("execution_status") == "error":
        chain = error_coder_chain
        prompt_input.update({"code": code, "traceback": traceback})
    else:
        chain = normal_coder_chain

    response: CoderOutput = chain.invoke(prompt_input)

    # Trả về code mới và reset status để executor chạy
    return {
        "code": response.code,
        "execution_status": None,
        "execution_error": None,
        "traceback": None,
        "execution_output": None
    }
