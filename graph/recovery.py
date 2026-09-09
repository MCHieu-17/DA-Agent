"""Recovery budgets live here; routers do not mutate state."""
import configuration as cfg

def fail(reason):
    return {"workflow_status": "failed", "termination_reason": reason}

def request_replan(state, reason):
    if state.get("replan_count", 0) >= cfg.MAX_REPLANS:
        return {**fail(f"Replan budget exhausted. {reason}"), "replan_reason": None}
    return {"replan_reason": reason}

def model_failure(node, exc):
    detail = f"{node}: {type(exc).__name__}: {exc}"
    return {**fail(detail), "node_error": detail}
