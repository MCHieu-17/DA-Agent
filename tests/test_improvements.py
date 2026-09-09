import json
from pathlib import Path
import subprocess
import sys
import time
import pytest
import configuration as cfg

def test_output_assertions_report_output_column_contract():
    from graph.nodes.planner import check_plan
    from conftest import plan
    candidate = plan()
    candidate['steps'][0]['expected_output'].update(
        type='table', columns=['month', 'revenue'], unique_columns=['Order Date'])
    profiles = [{'dataset_id': 'dataset_1', 'columns': [{'name': 'Sales'}]}]
    # Use the fixture's declared inputs so this exercises the output gate.
    profiles[0]['columns'] = [{'name': c} for c in candidate['steps'][0]['inputs'][0]['columns']]
    with pytest.raises(ValueError, match="Order Date.*month.*revenue"):
        check_plan(candidate, profiles)
    candidate['steps'][0]['expected_output']['unique_columns'] = ['month']
    check_plan(candidate, profiles)
    candidate['steps'][0]['expected_output'].update(type='scalar', columns=[], unique_columns=[], row_count=1)
    with pytest.raises(ValueError, match='null for scalar/chart'):
        check_plan(candidate, profiles)

def test_chat_skips_profiling(agent, request_state, monkeypatch):
    app, models = agent
    import graph.sources as sources
    monkeypatch.setattr(sources, "prepare_sources", lambda *a: pytest.fail("Chat scanned data"))
    models.set("router", {"intent": "chat", "response": "Xin chào"})
    state = app.invoke(request_state)
    assert models.calls == ["router"]
    assert state["workflow_status"] == "success"
    assert state["metrics"][0]["node"] == "intake"

def test_router_outage_is_failure(agent, request_state):
    app, models = agent
    models.set("router", RuntimeError("transport failed"))
    state = app.invoke(request_state)
    assert state["workflow_status"] == "failed"
    assert models.calls == ["router"]

def test_context_preserves_json_and_omits_unrelated_code():
    from graph.utils import analysis_context
    from langchain_core.messages import HumanMessage
    from conftest import plan
    state = {"messages": [HumanMessage(content="sum")], "profiles": [], "plan": plan(),
             "current_step_index": 0, "step_results": [{"ref": "step_1", "type": "table", "code": "SECRET_CODE",
             "directory": "HOST_SECRET", "preview": [{"x": "abc" * 1000} for _ in range(50)]}]}
    context = analysis_context(state, "synthetic")
    parsed = json.loads(context["evidence"])
    assert parsed[0]["preview_truncated"]
    assert "SECRET_CODE" not in context["evidence"]
    assert "HOST_SECRET" not in context["evidence"]

def test_required_code_is_not_silently_cut(monkeypatch):
    from graph.utils import analysis_context
    from langchain_core.messages import HumanMessage
    monkeypatch.setattr(cfg, "VERIFICATION_EVIDENCE_MAX_CHARS", 50)
    with pytest.raises(ValueError, match="Required evidence"):
        analysis_context({"messages": [HumanMessage(content="sum")], "step_results": [
            {"ref": "step_1", "code": "x" * 200}]})

def test_snapshot_projects_columns_and_preserves_ids(tmp_path, monkeypatch):
    from graph.sources import snapshot_file
    import pandas as pd
    monkeypatch.setattr(cfg, "SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    source = tmp_path / "data.csv"
    source.write_text("id,amount,secret\n001,10,password\n002,20,key\n", encoding="utf-8")
    first = snapshot_file(source, ["id", "amount"])
    assert snapshot_file(source, ["id", "amount"]) == first
    result = pd.read_parquet(first)
    assert list(result.columns) == ["id", "amount"]
    assert result["id"].tolist() == ["001", "002"]
    source.write_text("id,amount,secret\n003,99,new\n", encoding="utf-8")
    assert snapshot_file(source, ["id", "amount"]) != first
    assert pd.read_parquet(first)["id"].tolist() == ["001", "002"]

def test_production_source_boundary(tmp_path, monkeypatch):
    from graph.sources import authorized_sources
    monkeypatch.setattr(cfg, "ENVIRONMENT", "production")
    with pytest.raises(PermissionError):
        authorized_sources({"file_paths": ["/etc/passwd"]})
    catalog = tmp_path / "sources.json"
    catalog.write_text(json.dumps({"sales": {"kind": "file", "path": "x", "users": ["alice"], "columns": ["Sales"]}}))
    monkeypatch.setattr(cfg, "SOURCE_REGISTRY_PATH", str(catalog))
    with pytest.raises(PermissionError):
        authorized_sources({"principal": "bob", "source_refs": ["sales"]})
    assert authorized_sources({"principal": "alice", "source_refs": ["sales"]})[0]["columns"] == ["Sales"]

@pytest.mark.parametrize("sql", ["DELETE FROM dataset_1", "SELECT 1; SELECT 2", "SELECT * FROM secret",
    "SELECT * FROM read_csv('/etc/passwd')", "SELECT pg_sleep(10)", "SELECT public.lower('x')",
    "COPY dataset_1 TO '/tmp/a'", "SELECT * INTO x FROM dataset_1",
    "WITH x AS (DELETE FROM dataset_1 RETURNING *) SELECT * FROM x"])
def test_sql_policy_rejects_escape(sql):
    from graph.sql_policy import validate_sql
    with pytest.raises(ValueError):
        validate_sql(sql, {"dataset_1"}, "postgres")

def test_duckdb_cte_and_result_contract(python_state):
    from graph.nodes.execution import run_python
    python_state["plan"]["steps"][0]["engine"] = "duckdb_sql"
    result = run_python({**python_state, "code": "WITH x AS (SELECT CAST(Sales AS DOUBLE) AS v FROM dataset_1) SELECT SUM(v) FROM x"})
    assert result["execution_status"] == "success", result
    assert result["result"]["value"] == 30

def test_read_result_does_not_read_entire_dataframe(tmp_path, monkeypatch):
    import pandas as pd
    from graph.runtime import read_result
    frame = pd.DataFrame({"x": range(100_000)})
    frame.to_parquet(tmp_path / "result.parquet", row_group_size=1000)
    (tmp_path / "result.json").write_text('{"type":"table","file":"result.parquet"}')
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("Full table load"))
    result = read_result(tmp_path, {"type": "table", "columns": ["x"]})
    assert result["row_count"] == 100_000
    assert len(result["preview"]) == cfg.RESULT_PREVIEW_ROWS

def test_local_secret_not_inherited(python_state, monkeypatch):
    from graph.nodes.execution import run_python
    monkeypatch.setenv("GEMINI_API_KEY", "fake-secret-for-test")
    result = run_python({**python_state, "code": "import os\nsave_scalar(os.getenv('GEMINI_API_KEY'))"})
    assert result["result"]["value"] is None

def test_log_limit(python_state, monkeypatch):
    from graph.nodes.execution import run_python
    monkeypatch.setattr(cfg, "EXECUTION_LOG_MAX_BYTES", 4096)
    result = run_python({**python_state, "code": "print('x'*100000)\nsave_scalar(1)"})
    assert result["execution_status"] == "error"
    assert "OutputLimitExceeded" in result["traceback"]

def test_production_never_falls_back(monkeypatch):
    from graph.executors import preflight
    monkeypatch.setattr(cfg, "ENVIRONMENT", "production")
    monkeypatch.setattr(cfg, "EXECUTOR_BACKEND", "local")
    with pytest.raises(RuntimeError, match="prohibited"):
        preflight()

def test_container_hardening_flags():
    from graph.executors import container_command
    args = container_command("test", "image", [("/input", "/inputs", True)], ["python"])
    for flag in ["--runtime=runsc", "--network=none", "--read-only", "--cap-drop=ALL", "--pids-limit=128"]:
        assert flag in args
    assert "type=bind,src=/input,dst=/inputs,readonly" in args

def test_budget_stops_before_model_call():
    from graph.telemetry import ledger, reserve, BudgetExceeded
    from langchain_core.prompt_values import StringPromptValue
    token = ledger.set({"charge": cfg.RUN_TOKEN_BUDGET, "deadline": time.time() + 30, "events": []})
    try:
        with pytest.raises(BudgetExceeded):
            reserve("coder", StringPromptValue(text="hello"), 2048)
    finally:
        ledger.reset(token)

def test_provider_budgets_survive_structured_output():
    # Separate interpreter: graph fixture intentionally replaces graph.llms.
    script = '''
from graph.llms import create_llm
from graph.state import RouteDecision
for provider, model, key in [('gemini','gemini-3.5-flash-lite','max_output_tokens'),('deepseek','deepseek-v4-flash','max_tokens'),('self_host','gemma4:12b','num_predict')]:
    opts = {key: 64}
    if provider != 'self_host': opts['api_key'] = 'offline-placeholder'
    llm = create_llm(provider, model, opts)
    chain = llm.with_structured_output(RouteDecision)
    assert getattr(chain.first.bound, key) == 64, provider
'''
    process = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr

def test_api_rejects_arbitrary_state():
    from service.api import Request
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Request.model_validate({"messages": [{"content": "hello"}], "file_paths": ["/etc/passwd"]})
    with pytest.raises(ValidationError):
        Request.model_validate({"messages": [{"content": "hello", "role": "ai"}]})

def test_result_assertions_reject_duplicate_groups(tmp_path):
    import pandas as pd
    from graph.runtime import read_result
    pd.DataFrame({"city": ["A", "A"], "sales": [10, 20]}).to_parquet(tmp_path / "result.parquet")
    (tmp_path / "result.json").write_text('{"type":"table","file":"result.parquet"}')
    with pytest.raises(ValueError, match="assertions failed"):
        read_result(tmp_path, {"type": "table", "columns": ["city", "sales"], "unique_columns": ["city"]})

def test_missing_usage_is_estimated_and_actual_usage_recorded():
    from graph.telemetry import ledger, record_call
    from langchain_core.messages import AIMessage
    current = {"charge": 1000, "deadline": time.time() + 30, "events": []}
    token = ledger.set(current)
    try:
        record_call("coder", time.perf_counter(), 500)
        assert current["charge"] == 1000
        assert current["events"][-1]["usage"] is None
        raw = AIMessage(content="ok", usage_metadata={"input_tokens": 80, "output_tokens": 20, "total_tokens": 100})
        record_call("coder", time.perf_counter(), 500, raw)
        assert current["charge"] == 600
        assert current["events"][-1]["usage"]["total_tokens"] == 100
    finally:
        ledger.reset(token)

def test_native_parquet_timestamps_are_not_ambiguous(tmp_path):
    import pandas as pd
    from graph.nodes.data_profiling import profile_file
    file = tmp_path / "dates.parquet"
    pd.DataFrame({"date": pd.to_datetime(["2024-01-02", "2024-02-01"], utc=True)}).to_parquet(file)
    column = profile_file(file, "dataset_1")["columns"][0]
    assert column["datetime"]["native"]
    assert not column["datetime"]["ambiguous"]

def test_missing_sandbox_does_not_spend_debug_tokens(agent, request_state, monkeypatch):
    from graph import executors
    def missing():
        raise executors.ExecutorUnavailable("runsc missing")
    monkeypatch.setattr(executors, "preflight", missing)
    app, models = agent
    result = app.invoke(request_state)
    assert result["workflow_status"] == "failed"
    assert "debugger" not in models.calls
    assert models.calls.count("planner") == 1
