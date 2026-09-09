import json
import sys
from pathlib import Path
import pytest
from graph.nodes.execution import run_python
from graph.executors import ExecutionResult, is_transient_bootstrap_error

def run(state, code, kind="scalar", columns=None):
    state["plan"]["steps"][0]["expected_output"] = {"type": kind, "columns": columns or [], "description": "test"}
    return run_python({**state, "code": code})

def test_same_interpreter_env_cwd_and_utf8(python_state, monkeypatch):
    monkeypatch.setenv("DA_TEST_MARKER", "local")
    result = run(python_state,
        "import os,sys,json\nprint('Xin chào')\nsave_scalar(json.dumps([sys.executable,os.getcwd(),os.environ.get('DA_TEST_MARKER')]))")
    assert result["execution_status"] == "success", result
    interpreter, cwd, marker = json.loads(result["result"]["value"])
    from graph.utils import get_project_root
    assert Path(interpreter) == Path(sys.executable)
    assert Path(cwd) == get_project_root()
    assert marker is None
    assert "Xin chào" in result["execution_output"]

@pytest.mark.parametrize("code", ["", " ", "syntax !!!", "raise RuntimeError('bad')", "print('no result')"])
def test_invalid_execution_returns_error(python_state, code):
    result = run(python_state, code)
    assert result["execution_status"] == "error"
    assert "result" not in result

def test_partial_artifacts_not_published(python_state):
    result = run(python_state, "from pathlib import Path\nPath(ARTIFACTS_DIR,'partial.csv').write_text('bad')\nsave_scalar(30)\nraise ValueError('failed')")
    assert result["execution_status"] == "error"
    assert "result" not in result

def test_timeout_keeps_partial_unicode_stdout(python_state):
    python_state["execution_timeout_seconds"] = 3
    result = run(python_state, "import time\nprint('Đã bắt đầu',flush=True)\ntime.sleep(30)\nsave_scalar(1)")
    assert result["execution_error"] == "TimeoutExpired"
    assert "Đã bắt đầu" in result["execution_output"]

def test_local_executor_retries_trusted_runtime_bootstrap(python_state, monkeypatch):
    import graph.executors as executors
    real_process = executors.bounded_process
    calls = []

    def fail_bootstrap_once(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 1:
            return ExecutionResult(
                1, "",
                'Importing the NumPy C-extensions failed: '
                'PyCapsule_Import could not import module "datetime"',
            )
        return real_process(*args, **kwargs)

    monkeypatch.setattr(executors, "bounded_process", fail_bootstrap_once)
    result = run(python_state, "save_scalar(1)")
    assert result["execution_status"] == "success", result
    assert len(calls) == 2


def test_runtime_bootstrap_signature_is_not_a_generic_code_error():
    assert is_transient_bootstrap_error(
        'PyCapsule_Import could not import module "datetime"'
    )
    assert not is_transient_bootstrap_error("ValueError: generated code is wrong")


def test_schema_mismatch_fails(python_state):
    result = run(python_state, "import pandas as pd\nsave_table(pd.DataFrame({'wrong':[1]}))", "table", ["Sales"])
    assert result["execution_status"] == "error"
    assert "Missing expected columns" in result["traceback"]

def test_empty_table_is_valid(python_state):
    result = run(python_state, "import pandas as pd\nsave_table(pd.DataFrame({'Sales':pd.Series([],dtype='float64')}))", "table", ["Sales"])
    assert result["execution_status"] == "success", result
    assert result["result"]["row_count"] == 0

def test_parquet_preserves_identifiers_dates_and_nullable_numbers(python_state):
    result = run(python_state, """import pandas as pd
save_table(pd.DataFrame({
    'id': pd.Series(['001', '002'], dtype='string'),
    'date': pd.to_datetime(['2020-01-01', '2020-01-02']),
    'count': pd.Series([1, None], dtype='Int64'),
}))""", "table", ["id", "date", "count"])
    assert result["execution_status"] == "success", result
    import pandas as pd
    frame = pd.read_parquet(result["result"]["path"])
    assert frame["id"].tolist() == ["001", "002"]
    assert str(frame["count"].dtype) == "Int64"
    assert str(frame["date"].dtype).startswith("datetime64")

def test_supermarket_monthly_oracle_and_chart_exports(python_state):
    import pandas as pd
    from graph.nodes.data_profiling import data_profiling_node
    from graph.utils import get_project_root
    path = get_project_root() / "datasets" / "SuperMarket Analysis.csv"
    state = {**python_state, **data_profiling_node({"file_paths": [str(path)]})}
    state["plan"] = python_state["plan"]
    state["plan"]["steps"][0]["inputs"][0]["columns"] = ["Date", "Sales"]
    result = run(state, """from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
df = load_input('dataset_1')
df['month'] = pd.to_datetime(df['Date'], format='%m/%d/%Y').dt.strftime('%Y-%m')
df['Sales'] = pd.to_numeric(df['Sales'])
monthly = df.groupby('month', as_index=False)['Sales'].sum().rename(columns={'Sales':'revenue'})
monthly.to_csv(Path(ARTIFACTS_DIR,'monthly.csv'),index=False)
plt.plot(monthly['month'],monthly['revenue'])
plt.savefig(Path(ARTIFACTS_DIR,'monthly.png'))
px.line(monthly,x='month',y='revenue').write_html(Path(ARTIFACTS_DIR,'monthly.html'))
save_table(monthly)
""", "table", ["month", "revenue"])
    assert result["execution_status"] == "success", result
    frame = pd.read_parquet(result["result"]["path"])
    assert frame["month"].tolist() == ["2019-01", "2019-02", "2019-03"]
    assert frame["revenue"].sum() == pytest.approx(322966.749)
    # Independent published/manual oracle, not the same groupby implementation.
    assert frame["revenue"].tolist() == pytest.approx([116291.868, 97219.374, 109455.507])
    assert {Path(p).suffix for p in result["result"]["artifacts"]} == {".csv", ".png", ".html"}

def test_double_emit_and_wrong_output_kind_fail(python_state):
    assert run(python_state, "save_scalar(1)\nsave_scalar(2)")["execution_status"] == "error"

def test_failed_directory_creation_is_controlled(python_state, monkeypatch, tmp_path):
    import graph.utils as utils
    target = tmp_path / "file"
    target.write_text("keep")
    monkeypatch.setattr(utils, "ARTIFACTS_DIR", str(target))
    result = run(python_state, "save_scalar(1)")
    assert result["execution_status"] == "error"
    assert target.read_text() == "keep"

def test_source_columns_are_restricted(python_state):
    assert run(python_state, "save_scalar(load_input('dataset_1')['City'].iloc[0])")["execution_status"] == "error"
