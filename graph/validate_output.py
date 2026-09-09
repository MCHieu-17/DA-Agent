"""Trusted validator entrypoint; run in a fresh read-only sandbox in production."""
import json
from pathlib import Path
import sys
from graph.runtime import read_result

if __name__ == "__main__":
    result = read_result(sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
