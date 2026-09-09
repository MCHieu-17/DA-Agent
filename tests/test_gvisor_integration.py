"""Linux release gate: DA_TEST_GVISOR=1 and a pinned DA_SANDBOX_IMAGE are required."""
import os
import pytest
import configuration as cfg

pytestmark = pytest.mark.skipif(os.getenv("DA_TEST_GVISOR") != "1", reason="Real Linux gVisor release gate")

@pytest.fixture
def sandbox(python_state, monkeypatch):
    monkeypatch.setattr(cfg, "EXECUTOR_BACKEND", "gvisor")
    monkeypatch.setattr(cfg, "SANDBOX_DISK_MB", 256)
    monkeypatch.setattr(cfg, "ENVIRONMENT", "production")
    return python_state

def test_real_isolation(sandbox, monkeypatch):
    from graph.nodes.execution import run_python
    monkeypatch.setenv("DA_SECRET_CANARY", "must-not-leak")
    code = '''
import os, socket
from pathlib import Path
assert os.getenv('DA_SECRET_CANARY') is None
assert not Path('/var/run/docker.sock').exists()
try:
    Path('/inputs/dataset_1.parquet').write_text('tamper')
    raise AssertionError('input writable')
except OSError:
    pass
for address in [('1.1.1.1', 443), ('169.254.169.254', 80)]:
    try:
        socket.create_connection(address, timeout=1)
        raise AssertionError('network available')
    except OSError:
        pass
save_scalar(30)
'''
    result = run_python({**sandbox, "code": code})
    assert result["execution_status"] == "success", result
    assert result["result"]["value"] == 30

@pytest.mark.parametrize("code", [
    "from pathlib import Path\nPath(ARTIFACTS_DIR,'escape.csv').symlink_to('/etc/passwd')\nsave_scalar(1)",
    "while True: print('x'*10000,flush=True)",
    "import time\ntime.sleep(600)",
    "x=bytearray(6*1024**3)\nsave_scalar(1)",
    "import subprocess,sys\nwhile True: subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])",
    "from pathlib import Path\nwith Path(ARTIFACTS_DIR,'large.csv').open('wb') as f:\n while True: f.write(b'x'*8*1024**2)",
])
def test_real_limits(sandbox, code):
    from graph.nodes.execution import run_python
    result = run_python({**sandbox, "execution_timeout_seconds": 10, "code": code})
    assert result["execution_status"] == "error"

def test_child_cannot_modify_sealed_result_after_exit(sandbox):
    from graph.nodes.execution import run_python
    from pathlib import Path
    import time
    code = '''
import subprocess, sys
subprocess.Popen([sys.executable, '-c', "import time; from pathlib import Path; time.sleep(2); Path('/outputs/late.csv').write_text('tamper')"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
save_scalar(1)
'''
    result = run_python({**sandbox, "code": code})
    assert result["execution_status"] == "success", result
    time.sleep(3)
    assert not Path(result["result"]["directory"], "late.csv").exists()
