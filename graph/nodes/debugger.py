from graph.state import DataAgentState


def debug_node(state: DataAgentState):
    """Keep only compact error context; the coder performs the repair in one call."""
    trace = (state.get("traceback") or "")[-4000:]
    return {"debug_feedback": f"{state.get('execution_error', 'ExecutionError')}: {trace}"}
