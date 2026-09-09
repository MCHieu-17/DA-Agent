"""Reproducible storage/execution benchmark (no LLM); does not claim inference speed."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size-mb", type=int, default=100, choices=[100, 1000, 10000])
    parser.add_argument("--concurrency", type=int, default=1, choices=[1, 5])
    args = parser.parse_args()
    from graph.sources import snapshot_file
    from graph.nodes.execution import run_python
    import configuration as cfg
    directory = Path(cfg.ARTIFACTS_DIR).resolve() / "benchmarks" / uuid4().hex
    directory.mkdir(parents=True)
    csv = directory / "input.csv"
    row = b"001,10,A\n"
    count = args.size_mb * 1024 ** 2 // len(row)
    with csv.open("wb") as stream:
        stream.write(b"id,Sales,City\n")
        remaining = count
        while remaining:
            batch = min(remaining, 100_000)
            stream.write(row * batch)
            remaining -= batch
    started = time.perf_counter()
    snapshot = snapshot_file(csv)
    snapshot_seconds = time.perf_counter() - started
    step = {"step": 1, "engine": "duckdb_sql", "goal": "Sum Sales", "operation": "Sum",
            "inputs": [{"source": "dataset_1", "columns": ["Sales"]}],
            "expected_output": {"type": "scalar", "columns": [], "description": "Total"}}
    def execute(_):
        begin = time.perf_counter()
        state = {"artifact_run_id": uuid4().hex, "plan_version": 0, "debug_count": 0,
                 "plan": {"steps": [step]}, "current_step_index": 0,
                 "profiles": [{"dataset_id": "dataset_1", "path": snapshot, "read_options": {}}],
                 "code": 'SELECT SUM(CAST("Sales" AS DOUBLE)) FROM dataset_1', "execution_timeout_seconds": 300}
        result = run_python(state)
        return {"seconds": time.perf_counter()-begin, "passed": result.get("result", {}).get("value") == count*10,
                "error": result.get("traceback")}
    begin = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        runs = list(pool.map(execute, range(args.concurrency)))
    report = {"backend": cfg.EXECUTOR_BACKEND, "source_bytes": csv.stat().st_size, "rows": count,
              "concurrency": args.concurrency, "snapshot_seconds": snapshot_seconds,
              "execution_wall_seconds": time.perf_counter()-begin, "runs": runs}
    target = directory / "report.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {target}")
    return 0 if all(r["passed"] for r in runs) else 1

if __name__ == "__main__":
    raise SystemExit(main())
