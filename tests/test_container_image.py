"""Packaging smoke test with trusted fixture code; this is NOT a gVisor isolation test."""
import json
import os
from pathlib import Path
import subprocess
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DA_TEST_SANDBOX_IMAGE"), reason="Sandbox image not configured")

def test_image_runtime_and_validator(tmp_path):
    image = os.environ["DA_TEST_SANDBOX_IMAGE"]
    job = tmp_path / "job"
    output = tmp_path / "output"
    job.mkdir(); output.mkdir()
    output.chmod(0o777)
    expected = {"type": "table", "columns": ["x"], "unique_columns": ["x"], "row_count": 2}
    (job / "context.json").write_text(json.dumps({"inputs": {}, "output_dir": "/outputs"}))
    (job / "expected.json").write_text(json.dumps(expected))
    (job / "code.py").write_text("import pandas as pd\nsave_table(pd.DataFrame({'x':[1,2]}))\n")
    common = ["docker", "run", "--rm", "--network=none", "--read-only", "--user=65534:65534",
              "--tmpfs=/tmp:rw,size=134217728", "--mount", f"type=bind,src={job},dst=/job,readonly"]
    executed = subprocess.run([*common, "--mount", f"type=bind,src={output},dst=/outputs", image,
        "python", "-m", "graph.runtime", "/job/context.json", "/job/code.py"], capture_output=True, text=True, timeout=60)
    assert executed.returncode == 0, executed.stderr
    validated = subprocess.run([*common, "--mount", f"type=bind,src={output},dst=/outputs,readonly", image,
        "python", "-m", "graph.validate_output", "/outputs", "/job/expected.json"], capture_output=True, text=True, timeout=60)
    assert validated.returncode == 0, validated.stderr
    result = json.loads(validated.stdout)
    assert result["row_count"] == 2
    assert result["checks"]["unique"]
