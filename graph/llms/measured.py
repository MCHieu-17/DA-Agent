"""Capture raw structured responses and account for every transport attempt."""
import threading
import time
from langchain_core.runnables import RunnableLambda
from graph.telemetry import reserve, record_call, check_deadline
import configuration as cfg

_slots = threading.BoundedSemaphore(cfg.LLM_MAX_CONCURRENCY)

class MeasuredModel(RunnableLambda):
    def __init__(self, name, model):
        self.node_name, self.model = name, model
        super().__init__(lambda prompt: self._call(prompt))

    def with_structured_output(self, schema):
        runnable = self.model.with_structured_output(schema, include_raw=True)
        return RunnableLambda(lambda prompt: self._call(prompt, runnable))

    def _call(self, prompt, structured=None):
        for attempt in range(cfg.LLM_MAX_RETRIES + 1):
            estimate = reserve(self.node_name, prompt, cfg.LLM_NODE_MAX_OUTPUT_TOKENS[self.node_name])
            started = time.perf_counter()
            raw = None
            try:
                while not _slots.acquire(timeout=.25):
                    check_deadline()
                try:
                    check_deadline()
                    response = (structured or self.model).invoke(prompt)
                finally:
                    _slots.release()
                if structured:
                    raw = response["raw"]
                    if response.get("parsing_error"):
                        raise response["parsing_error"]
                    if response.get("parsed") is None:
                        raise ValueError("Structured response contained no parsed result.")
                    result = response["parsed"]
                else:
                    raw = result = response
                record_call(self.node_name, started, estimate, raw, attempt=attempt)
                return result
            except Exception as exc:
                record_call(self.node_name, started, estimate, raw, exc, attempt)
                # Never retry parsing, permission, or budget failures as outages.
                status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                retry = status in {429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError))
                retry = retry or type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "ServiceUnavailable", "ResourceExhausted"}
                if not retry or attempt == cfg.LLM_MAX_RETRIES:
                    raise
                time.sleep(min(2 ** attempt, 4))
