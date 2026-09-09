"""Per-run budgets and per-node telemetry, kept out of LLM prompts."""
from contextvars import ContextVar
from functools import wraps
import time
import configuration as cfg

ledger = ContextVar("da_ledger", default=None)

class BudgetExceeded(RuntimeError):
    pass

def check_deadline():
    current = ledger.get()
    if current and time.time() >= current["deadline"]:
        raise BudgetExceeded("Run deadline exceeded.")

def reserve(node, prompt, output_limit):
    check_deadline()
    current = ledger.get()
    # UTF-8 bytes are a conservative bound for tokenizers, not reported usage.
    estimate = len(prompt.to_string().encode("utf-8")) + output_limit + 2048
    if current:
        spare = 0 if node == "verification" else cfg.VERIFICATION_TOKEN_RESERVE
        if current["charge"] + estimate + spare > cfg.RUN_TOKEN_BUDGET:
            raise BudgetExceeded("Run token budget exhausted; verification reserve protected.")
        current["charge"] += estimate
    return estimate

def record_call(node, started, estimate, raw=None, error=None, attempt=0):
    current = ledger.get()
    usage = getattr(raw, "usage_metadata", None) or {}
    total = usage.get("total_tokens")
    event = {"kind": "llm", "node": node, "seconds": time.perf_counter() - started,
             "provider": cfg.LLM_PROVIDER, "model": cfg.LLM_MODEL, "attempt": attempt,
             "usage": usage or None, "estimated_token_charge": estimate,
             "error": type(error).__name__ if error else None}
    if current:
        if total is not None:
            current["charge"] += total - estimate
        current["events"].append(event)

def observed(name, node):
    @wraps(node)
    def invoke(state):
        new = name == "intake"
        current = {"deadline": time.time() + cfg.RUN_TIMEOUT_SECONDS if new else state.get("deadline", time.time() + cfg.RUN_TIMEOUT_SECONDS),
                   "charge": 0 if new else state.get("token_charge", 0), "events": []}
        token = ledger.set(current)
        started = time.perf_counter()
        try:
            if name != "finalize":
                check_deadline()
            update = node(state)
        except BudgetExceeded as exc:
            from graph.recovery import fail
            update = fail(str(exc))
        finally:
            ledger.reset(token)
        events = [] if new else state.get("metrics", [])
        return {**update, "deadline": current["deadline"], "token_charge": current["charge"],
                "metrics": [*events, *current["events"], {"kind": "node", "node": name,
                            "seconds": time.perf_counter() - started}]}
    return invoke
