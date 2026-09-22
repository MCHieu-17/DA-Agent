from graph.e2b_executor import cleanup_sandbox
from graph.state import DataAgentState


def cleanup_node(state: DataAgentState):
    cleanup_sandbox(state)
    return {"sandbox_id": None, "sandbox_file_map": {}}
