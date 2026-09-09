"""Semantic result oracles: named columns and keyed rows, not a bag of numbers."""
import math

def equal(actual, expected):
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        return isinstance(actual, (float, int)) and not isinstance(actual, bool) and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=.0001)
    return actual == expected

def matches(state, oracle):
    for result in reversed(state.get("step_results", [])):
        if result["type"] != oracle["type"]:
            continue
        if oracle["type"] == "scalar":
            if equal(result["value"], oracle["value"]):
                return True
        elif oracle["type"] == "table":
            if result.get("row_count") != len(oracle["rows"]):
                continue
            if not set(oracle["columns"]) <= set(result["columns"]):
                continue
            import pyarrow.parquet as pq
            rows = pq.read_table(result["path"], columns=oracle["columns"]).to_pylist()
            if not oracle.get("ordered", False):
                key = oracle["columns"][0]
                rows = sorted(rows, key=lambda row: str(row[key]))
                expected = sorted(oracle["rows"], key=lambda row: str(row[key]))
            else:
                expected = oracle["rows"]
            if all(all(equal(actual[col], wanted[col]) for col in oracle["columns"]) for actual, wanted in zip(rows, expected)):
                return True
    return False
