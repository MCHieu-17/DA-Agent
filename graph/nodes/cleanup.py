"""Release an optional E2B runtime without changing the completed answer."""

from graph.e2b_executor import cleanup_sandbox
from graph.state import DataAgentState


def cleanup_node(state: DataAgentState):
    if not state.get("sandbox_id"):
        return {}
    try:
        cleanup_sandbox(state)
    except Exception:
        # Cleanup is best effort and must never hide an already completed answer.
        pass
    return {"sandbox_id": None, "sandbox_file_map": {}}
