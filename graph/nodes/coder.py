from pathlib import Path

from configuration import EXECUTION_ALLOWED_IMPORTS
from graph.llms import get_node_llm
from graph.prompts import error_prompt, normal_prompt
from graph.state import CoderOutput, DataAgentState
from graph.utils import format_step_evidence, get_project_root, get_run_artifacts_dir


structured_coder_llm = get_node_llm("coder").with_structured_output(CoderOutput)
normal_coder_chain = normal_prompt | structured_coder_llm
error_coder_chain = error_prompt | structured_coder_llm


def coder_node(state: DataAgentState):
    plan = state.get("plan", [])
    current_idx = state.get("current_step_idx", 0)
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"

    schema_str = state.get("schema_str", "")
    past_steps = format_step_evidence(state.get("past_steps", []))
    code = state.get("code", "")
    traceback = state.get("traceback", "")
    project_dir = get_project_root()
    raw_artifacts_dir = Path(get_run_artifacts_dir(state)).expanduser()
    artifacts_path = (
        raw_artifacts_dir
        if raw_artifacts_dir.is_absolute()
        else project_dir / raw_artifacts_dir
    )
    artifacts_dir = state.get("execution_artifacts_dir") or str(
        artifacts_path.resolve(strict=False)
    )
    data_files = [
        str(Path(file_path).expanduser().resolve(strict=False))
        for file_path in state.get(
            "execution_file_paths", state.get("file_paths", [])
        )
    ]

    prompt_input = {
        "schema_str": schema_str,
        "past_steps": past_steps,
        "current_step": current_step,
        "artifacts_dir": artifacts_dir,
        "data_files": data_files,
        "allowed_imports": ", ".join(sorted(EXECUTION_ALLOWED_IMPORTS)),
    }

    if state.get("execution_status") == "error":
        chain = error_coder_chain
        prompt_input.update({
            "code": code,
            "traceback": traceback,
            "debug_feedback": state.get("debug_feedback", ""),
        })
    else:
        chain = normal_coder_chain

    try:
        response: CoderOutput = chain.invoke(prompt_input)
    except Exception as exc:
        return {
            "node_error": f"CoderError: {type(exc).__name__}: {exc}",
            "workflow_status": "failed",
        }

    # Trả về code mới và reset status để executor chạy
    return {
        "code": response.code,
        "execution_status": None,
        "execution_error": None,
        "traceback": None,
        "execution_output": None,
        "debug_feedback": None,
        "node_error": None,
    }
