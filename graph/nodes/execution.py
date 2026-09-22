from graph.e2b_executor import execute_code
from graph.state import DataAgentState


def execution_node(state: DataAgentState):
    # Built-in tools have already executed in tool_executor; this node only
    # normalizes their shared routing contract and must never create E2B.
    if state.get("action", {}).get("mode") == "tool":
        return {}
    index = state.get("current_step_idx", 0)
    step = state.get("plan", [])[index] if index < len(state.get("plan", [])) else {}
    try:
        result = execute_code(state)
    except Exception as exc:
        return {"execution_status": "error", "execution_error": type(exc).__name__, "traceback": str(exc), "retry_count": state.get("retry_count", 0) + 1}
    if not result["ok"]:
        return {"execution_status": "error", "execution_output": result.get("stdout", ""), "execution_error": result.get("error", "ExecutionError"), "traceback": result.get("traceback", result.get("stderr", "")), "retry_count": state.get("retry_count", 0) + 1, "sandbox_id": result["sandbox_id"], "sandbox_file_map": result["sandbox_file_map"]}
    record = {"step": step.get("objective", ""), "kind": "custom_compute", "action": "e2b_python", "status": "success", "summary": result.get("stdout", ""), "artifacts": result.get("artifacts", [])}
    return {"execution_status": "success", "execution_output": result.get("stdout", ""), "past_steps": state.get("past_steps", []) + [record], "execution_records": state.get("execution_records", []) + [record], "current_step_idx": index + 1, "artifacts": state.get("artifacts", []) + result.get("artifacts", []), "sandbox_id": result["sandbox_id"], "sandbox_file_map": result["sandbox_file_map"]}
