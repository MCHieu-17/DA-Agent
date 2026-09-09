"""Summarize evaluation reports without exposing prompts or source data."""
import argparse
import json
from pathlib import Path
import statistics

def summary(paths):
    runs = [r for path in paths for r in json.loads(Path(path).read_text(encoding="utf-8"))]
    seconds = sorted(r["seconds"] for r in runs if "seconds" in r)
    tokens = []
    for run in runs:
        calls = [e for e in run.get("metrics", []) if e["kind"] == "llm"]
        if calls and all(e.get("usage") is not None for e in calls):
            tokens.append(sum(e["usage"].get("input_tokens", 0) for e in calls))
    return {"runs": len(runs), "passed": sum(r["passed"] for r in runs),
            "p50_seconds": statistics.median(seconds) if seconds else None,
            "p95_seconds": seconds[min(len(seconds)-1, int(.95*len(seconds)))] if seconds else None,
            "median_input_tokens": statistics.median(tokens) if tokens else None,
            "runs_with_complete_token_usage": len(tokens)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+")
    parser.add_argument("--baseline", nargs="*")
    args = parser.parse_args()
    current = summary(args.reports)
    output = {"current": current}
    if args.baseline:
        previous = summary(args.baseline)
        output["baseline"] = previous
        before, after = previous["median_input_tokens"], current["median_input_tokens"]
        output["input_token_reduction"] = 1-after/before if before and after is not None else None
    print(json.dumps(output, indent=2))
