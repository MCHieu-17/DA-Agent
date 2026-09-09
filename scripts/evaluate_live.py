"""Opt-in live model acceptance cases. Never prints credentials."""
import argparse
import json
import math
from pathlib import Path
import sys
from datetime import datetime, timezone
import time
import statistics
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    return []

def main():
    parser = argparse.ArgumentParser()
    cases = json.loads(Path(__file__).with_name("live_cases.json").read_text(encoding="utf-8"))
    parser.add_argument("--case", choices=[c["id"] for c in cases])
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    from langchain_core.messages import HumanMessage
    from main import app
    from graph.utils import get_project_root
    from scripts.oracles import matches
    report = []
    for case in cases * args.repeat:
        if args.case and case["id"] != args.case:
            continue
        started = time.perf_counter()
        state = app.invoke({"messages": [HumanMessage(content=case["question"])],
                            "file_paths": [case["file"]]})
        evidence = [
            r.get("value") if r["type"] == "scalar" else r.get("preview", [])
            for r in state.get("step_results", [])
        ]
        observed = numbers(evidence)
        matched = matches(state, case["oracle"])
        passed = state["workflow_status"] == "success" and matched
        report.append({"case": case["id"], "passed": passed,
                       "workflow_status": state["workflow_status"], "oracle_matched": matched,
                       "final_answer": state.get("final_answer"), "verification": state.get("verification"),
                       "run_id": state["artifact_run_id"], "seconds": time.perf_counter() - started,
                       "metrics": state.get("metrics", []), "token_charge": state.get("token_charge"),
                       "provider": __import__("configuration").LLM_PROVIDER,
                       "model": __import__("configuration").LLM_MODEL})
        print(f"{case['id']}: {'PASS' if passed else 'FAIL'}")
    directory = get_project_root() / "artifacts" / "live_evaluations"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {path}")
    return 0 if all(r["passed"] for r in report) else 1

if __name__ == "__main__":
    raise SystemExit(main())
