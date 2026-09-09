"""Only model calls are fake; graph, profiling, and subprocesses are real."""
import os
os.environ.setdefault("DA_EXECUTOR_BACKEND", "local")
from collections import deque
from importlib import import_module
from types import ModuleType
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
import pytest

def plan(steps=None):
    return {"steps": steps or [{
        "step": 1, "goal": "Sum Sales",
        "inputs": [{"source": "dataset_1", "columns": ["Sales"]}],
        "operation": "Convert Sales to numbers and sum",
        "expected_output": {"type": "scalar", "columns": [], "description": "Total Sales"},
    }], "success_criteria": ["Report total Sales"]}

def verdict(decision="pass", refs=None):
    return {"decision": decision, "checks": [{
        "requirement": "Report total Sales", "status": "pass" if decision == "pass" else "fail",
        "evidence_refs": ["step_1"] if refs is None else refs, "reason": "Compared with computed total",
    }], "feedback": "Use the computed total and answer all requested parts.",
    "clarification_question": "Which revenue definition?" if decision == "clarify" else None}

class ScriptedModels:
    def __init__(self):
        self.responses, self.calls, self.prompts = {}, [], {}

    def set(self, name, *responses):
        self.responses[name] = deque(responses)

    def invoke(self, name, prompt, schema=None):
        self.calls.append(name)
        self.prompts.setdefault(name, []).append(prompt.to_string())
        defaults = {
            "router": {"intent": "analysis"},
            "clarify": {"reason": "Missing definition", "clarifying_question": "Which metric?"},
            "planner": plan(),
            "coder": {"code": "import pandas as pd\nsave_scalar(pd.to_numeric(load_input('dataset_1')['Sales']).sum())"},
            "debugger": {"code": "save_scalar(30)"},
            "synthetic": {"final_answer": "Total Sales: 30"},
            "verification": verdict(),
            "chat": AIMessage(content="Hello!"),
        }
        queue = self.responses.get(name)
        value = queue.popleft() if queue else defaults[name]
        if isinstance(value, Exception):
            raise value
        return schema.model_validate(value) if schema else value

    def get_node_llm(self, name):
        models = self
        class Model(RunnableLambda):
            def with_structured_output(self, schema):
                return RunnableLambda(lambda prompt: models.invoke(name, prompt, schema))
        return Model(lambda prompt: self.invoke(name, prompt))

@pytest.fixture(scope="session")
def graph_models():
    models = ScriptedModels()
    stub = ModuleType("graph.llms")
    from pathlib import Path
    stub.__path__ = [str(Path(__file__).resolve().parents[1] / "graph" / "llms")]
    stub.get_node_llm = models.get_node_llm
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(__import__("sys").modules, "graph.llms", stub)
        yield import_module("graph.graph").app, models

@pytest.fixture
def agent(graph_models, monkeypatch, tmp_path):
    app, models = graph_models
    models.responses.clear()
    models.calls.clear()
    models.prompts.clear()
    import graph.utils as utils
    monkeypatch.setattr(utils, "ARTIFACTS_DIR", str(tmp_path / "outputs"))
    return app, models

@pytest.fixture
def request_state(tmp_path):
    # Snapshot cache is shared by content, but tests keep it in temporary storage.
    path = tmp_path / "dữ liệu mẫu.csv"
    path.write_text("Sales,City\n10,A\n20,B\n", encoding="utf-8")
    return {"messages": [HumanMessage(content="Tính tổng Sales")], "file_paths": [str(path)]}

@pytest.fixture
def python_state(request_state, monkeypatch, tmp_path):
    from graph.nodes.data_profiling import data_profiling_node
    import graph.utils as utils
    monkeypatch.setattr(utils, "ARTIFACTS_DIR", str(tmp_path / "outputs"))
    return {**request_state, **data_profiling_node(request_state), "plan": plan()}
