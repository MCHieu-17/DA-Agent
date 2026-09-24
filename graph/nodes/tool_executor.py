from graph.state import DataAgentState
from graph.tools import execute_tool


def tool_executor_node(state: DataAgentState):
    action = state.get("action", {})
    index = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    step = plan[index] if index < len(plan) else {}
    try:
        result = execute_tool(state, action.get("tool_name", ""), action.get("arguments", {}))
        record = {"step": step.get("objective", ""), "kind": step.get("kind"), "action": action.get("tool_name"), "status": "success", "result": result, "artifacts": result.get("artifacts", [])}
        return {"execution_status": "success", "execution_output": str(result), "past_steps": state.get("past_steps", []) + [record], "execution_records": state.get("execution_records", []) + [record], "current_step_idx": index + 1, "artifacts": state.get("artifacts", []) + result.get("artifacts", []), "tool_retry_count": 0}
    except Exception as exc:
        record = {"step": step.get("objective", ""), "kind": step.get("kind"), "action": action.get("tool_name"), "status": "error", "error": f"{type(exc).__name__}: {exc}"}
        return {"execution_status": "error", "execution_error": type(exc).__name__, "traceback": str(exc), "past_steps": state.get("past_steps", []) + [record], "execution_records": state.get("execution_records", []) + [record], "tool_retry_count": state.get("tool_retry_count", 0) + 1}
