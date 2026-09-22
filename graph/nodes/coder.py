<<<<<<< HEAD
import json
from graph.llms import get_node_llm
from graph.prompts import coder_prompt
from graph.state import CodeOutput
from graph.recovery import model_failure
from graph.utils import analysis_context, current_step

def coder_node(state):
    try:
        result = (coder_prompt | get_node_llm("coder").with_structured_output(CodeOutput)).invoke({
            **analysis_context(state, "coder"), "current_step": json.dumps(current_step(state), ensure_ascii=False),
        })
        return {"code": result.code, "execution_status": None, "execution_error": None,
                "execution_output": None, "traceback": None}
    except Exception as exc:
        return model_failure("Coder", exc)
=======
from graph.llms import llm
from graph.e2b_executor import sandbox_file_map
from graph.prompts import error_prompt, normal_prompt
from graph.state import CoderOutput, DataAgentState

coder_llm = llm.with_structured_output(CoderOutput)
normal_coder_chain = normal_prompt | coder_llm
error_coder_chain = error_prompt | coder_llm


def coder_node(state: DataAgentState):
    index = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    step = plan[index] if index < len(plan) else {"objective": "Complete the requested analysis."}
    if state.get("execution_status") == "error":
        response = error_coder_chain.invoke({"current_step": step.get("objective", ""), "sandbox_file_map": state.get("sandbox_file_map") or sandbox_file_map(state), "code": state.get("code", ""), "traceback": state.get("debug_feedback") or state.get("traceback", "")})
    else:
        response = normal_coder_chain.invoke({"current_step": step.get("objective", ""), "assumptions": state.get("assumptions", []), "sandbox_file_map": state.get("sandbox_file_map") or sandbox_file_map(state), "past_steps": state.get("past_steps", [])[-5:]})
    return {"code": response.code, "execution_status": None, "execution_error": None, "traceback": None, "execution_output": None}
>>>>>>> restore-work
