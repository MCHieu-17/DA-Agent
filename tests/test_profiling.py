import json
from pathlib import Path
import pytest
import configuration as cfg
from graph.nodes import data_profiling as profiling

def make_profile(tmp_path, text):
    path = tmp_path / "input.csv"
    path.write_text(text, encoding="utf-8")
    return profiling.profile_file(path, "dataset_1")

def test_cache_reuses_profile_but_resets_workflow(request_state, monkeypatch):
    first = profiling.data_profiling_node(request_state)
    monkeypatch.setattr(profiling, "profile_file", lambda *args: pytest.fail("Cache miss"))
    second = profiling.data_profiling_node({**request_state, **first, "replan_count": 1, "draft_answer": "old", "step_results": [{"old": True}]})
    assert second["profiles"] == first["profiles"]
    assert second["artifact_run_id"] != first["artifact_run_id"]
    assert second["replan_count"] == 0
    assert second["draft_answer"] is None
    assert second["step_results"] == []

def test_file_and_config_changes_invalidate_cache(request_state, monkeypatch):
    first = profiling.data_profiling_node(request_state)
    monkeypatch.setattr(cfg, "PROFILE_SAMPLE_ROWS", 1)
    second = profiling.data_profiling_node({**request_state, **first})
    assert second["profile_cache_key"] != first["profile_cache_key"]
    Path(request_state["file_paths"][0]).write_text("Sales,City\n50,A\n", encoding="utf-8")
    third = profiling.data_profiling_node({**request_state, **second})
    assert third["profile_cache_key"] != second["profile_cache_key"]
    assert third["profiles"][0]["row_count"] == 1

@pytest.mark.parametrize("text", ["", "x,x\n1,2", ",x\n1,2", 'x,y\n"unclosed'])
def test_bad_csv_rejected(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    result = profiling.data_profiling_node({"file_paths": [str(path)]})
    assert not result["profile_valid"]
    assert result["profile_errors"]

def test_header_only_needs_input(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("x,y\n")
    assert not profiling.data_profiling_node({"file_paths": [str(path)]})["profile_valid"]


def test_cached_errors_do_not_accumulate(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("x,y\n")
    state = {"file_paths": [str(path)]}
    first = profiling.data_profiling_node(state)
    second = profiling.data_profiling_node({**state, **first})
    assert second["profile_errors"] == first["profile_errors"]

def test_mixed_types_and_leading_zeros_across_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "PROFILE_CHUNK_SIZE", 2)
    result = make_profile(tmp_path, "id,amount,empty\n001,10,\n002,20,\n003,oops,\n004,,\n")
    cols = {c["name"]: c for c in result["columns"]}
    assert cols["id"]["leading_zero_count"] == 4
    assert cols["id"]["suggested_type"] == "string"
    assert cols["amount"]["mixed_numeric"]
    assert cols["amount"]["numeric"]["mean"] == 15
    assert cols["amount"]["null_count"] == 1
    assert cols["empty"]["null_count"] == 4
    assert cols["empty"]["suggested_type"] == "unknown"

def test_ambiguous_dates_are_not_guessed(tmp_path):
    result = make_profile(tmp_path, "Date\n1/5/2019\n3/8/2019\n")
    assert result["columns"][0]["datetime"]["ambiguous"]
    assert result["columns"][0]["datetime"]["format"] is None

def test_unambiguous_dates_verified_on_all_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "PROFILE_SAMPLE_ROWS", 1)
    result = make_profile(tmp_path, "Date\n1/5/2019\n1/23/2019\n")
    dates = result["columns"][0]["datetime"]
    assert dates["format"] == "%m/%d/%Y"
    assert dates["formats"]["%m/%d/%Y"]["parse_rate"] == 1

def test_reservoir_is_bounded_reproducible_and_not_head(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "PROFILE_SAMPLE_ROWS", 10)
    monkeypatch.setattr(cfg, "PROFILE_EXAMPLE_ROWS", 10)
    result = make_profile(tmp_path, "x\n" + "\n".join(map(str, range(1000))))
    again = make_profile(tmp_path, "x\n" + "\n".join(map(str, range(1000))))
    sample = result["columns"][0]["sample"]
    assert result == again
    assert sample["rows"] == 10 and sample["scope"] == "sample"
    assert max(map(int, sample["examples"])) > 10
    assert result["columns"][0]["numeric"]["mean"] == 499.5

def test_summary_is_valid_bounded_json(tmp_path, monkeypatch):
    result = make_profile(tmp_path, "x,y\n1,a\n2,b\n")
    monkeypatch.setattr(cfg, "PROFILE_MAX_CHARS", 650)
    summary = profiling.summarize_profiles([result])
    assert len(summary) <= 650
    assert json.loads(summary)["omitted_details"]

def test_airbnb_missing_values_oracle():
    result = profiling.profile_file("datasets/AB_NYC_2019.csv", "dataset_1")
    assert result["row_count"] == 48895
    columns = {c["name"]: c for c in result["columns"]}
    assert columns["last_review"]["null_count"] == 10052
    assert columns["reviews_per_month"]["null_count"] == 10052

def test_relative_paths_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = profiling.profile_file("datasets/SuperMarket Analysis.csv", "dataset_1")
    assert result["row_count"] == 1000
