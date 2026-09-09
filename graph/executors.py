"""Bounded local development executor and fail-closed Linux gVisor executor."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4
import configuration as cfg

@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str

class ExecutorUnavailable(RuntimeError):
    """Infrastructure failure; code debugging cannot repair this."""

def bounded_process(command, *, cwd, env, timeout):
    """Drain both pipes continuously; cap stored bytes and kill on overflow/deadline."""
    import psutil
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    def drain(stream, target):
        while chunk := stream.read(4096):
            available = cfg.EXECUTION_LOG_MAX_BYTES - len(target)
            target.extend(chunk[:max(0, available)])
            if len(chunk) > available:
                overflow.set()
        stream.close()
    threads = [threading.Thread(target=drain, args=(stream, buffer), daemon=True)
               for stream, buffer in zip((process.stdout, process.stderr), buffers)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    error = None
    try:
        while process.poll() is None:
            if overflow.is_set() or time.monotonic() >= deadline:
                error = "OutputLimitExceeded" if overflow.is_set() else "TimeoutExpired"
                break
            time.sleep(.025)
    finally:
        if process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
            except psutil.NoSuchProcess:
                pass
        process.wait()
        for thread in threads:
            thread.join(timeout=2)
    out, err = [bytes(b).decode("utf-8", errors="replace") for b in buffers]
    if overflow.is_set():
        error = "OutputLimitExceeded"
    if error:
        if error == "TimeoutExpired":
            raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err)
        raise RuntimeError(error)
    return ExecutionResult(process.returncode, out, err)

_TRANSIENT_BOOTSTRAP_ERRORS = (
    'pycapsule_import could not import module "datetime"',
    "importing the numpy c-extensions failed",
)

def is_transient_bootstrap_error(stderr):
    """Errors raised while loading the trusted runtime, before generated code runs."""
    lowered = (stderr or "").lower()
    return any(marker in lowered for marker in _TRANSIENT_BOOTSTRAP_ERRORS)

def local_environment(runtime_directory=None):
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "CONDA_PREFIX"}
    environment = {**{k: v for k, v in os.environ.items() if k.upper() in allowed},
                   "MPLBACKEND": "Agg", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    if runtime_directory is not None:
        matplotlib_directory = Path(runtime_directory)
        matplotlib_directory.mkdir(exist_ok=True)
        environment["MPLCONFIGDIR"] = str(matplotlib_directory)
    return environment

def preflight():
    if cfg.EXECUTOR_BACKEND == "local":
        if cfg.ENVIRONMENT == "production":
            raise ExecutorUnavailable("Local executor is prohibited in production.")
        return
    if sys.platform != "linux" or not re.fullmatch(r"(?:[^\s]+@)?sha256:[a-f0-9]{64}", cfg.SANDBOX_IMAGE):
        raise ExecutorUnavailable("gVisor requires Linux and DA_SANDBOX_IMAGE pinned by sha256 digest.")
    for tool in ("docker", "mkfs.ext4", "mount", "umount"):
        if not shutil.which(tool):
            raise ExecutorUnavailable(f"Missing sandbox prerequisite: {tool}")
    try:
        info = subprocess.run(["docker", "info", "--format", "{{json .Runtimes}}"],
                              capture_output=True, text=True, timeout=10, check=True)
        subprocess.run(["docker", "image", "inspect", cfg.SANDBOX_IMAGE],
                       capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExecutorUnavailable("Docker daemon or pinned local image is unavailable.") from exc
    if "runsc" not in json.loads(info.stdout):
        raise ExecutorUnavailable("Docker runtime runsc is unavailable; refusing fallback.")

class DiskVolume:
    """Hard filesystem quota on a private sparse ext4 volume (not RAM-backed spill)."""
    def __init__(self, directory):
        self.directory = directory
        self.image = directory.parent / (directory.name + ".ext4")

    def __enter__(self):
        self.directory.mkdir()
        job_id = os.getenv("DA_JOB_ID")
        if job_id:
            register_volume(job_id, self.directory)
        needed = cfg.SANDBOX_DISK_MB * 1024 ** 2
        if shutil.disk_usage(self.directory).free < 2 * needed:
            raise ExecutorUnavailable("Insufficient disk reservation for sandbox and sealed outputs.")
        with self.image.open("xb") as stream:
            stream.truncate(needed)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-m", "0", str(self.image)], check=True, timeout=30)
        subprocess.run(["mount", "-o", "loop,nodev,nosuid,noexec", str(self.image), str(self.directory)], check=True, timeout=10)
        self.directory.chmod(0o777)
        (self.directory / "lost+found").rmdir()
        return self.directory

    def __exit__(self, *args):
        subprocess.run(["umount", str(self.directory)], check=True, timeout=10)
        self.image.unlink()
        self.directory.rmdir()

def container_command(name, image, mounts, command):
    args = ["docker", "create", "--name", name, "--runtime=runsc", "--network=none", "--read-only",
            "--user=65534:65534", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            f"--cpus={cfg.SANDBOX_CPUS}", f"--memory={cfg.SANDBOX_MEMORY_MB}m",
            f"--memory-swap={cfg.SANDBOX_MEMORY_MB}m", f"--pids-limit={cfg.SANDBOX_PIDS}",
            "--log-driver=none", "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=134217728,mode=1777",
            "--env=MPLBACKEND=Agg", "--env=MPLCONFIGDIR=/tmp/mpl", "--env=HOME=/tmp",
            "--env=PYTHONUNBUFFERED=1", "--workdir=/outputs", "--label=da-agent.sandbox=true"]
    for source, target, readonly in mounts:
        args += ["--mount", f"type=bind,src={source},dst={target}" + (",readonly" if readonly else "")]
    if os.getenv("DA_JOB_ID"):
        args += ["--label", "da-agent.job=" + os.environ["DA_JOB_ID"]]
    return [*args, image, *command]

def launch(mounts, command, timeout):
    name = "da-" + uuid4().hex
    subprocess.run(container_command(name, cfg.SANDBOX_IMAGE, mounts, command),
                   capture_output=True, text=True, check=True, timeout=15)
    try:
        return bounded_process(["docker", "start", "--attach", name], cwd=None, env=None, timeout=timeout)
    finally:
        # Kill even if the initial Python process exited but left descendants.
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15, check=True)

def execute(directory, context, code, timeout):
    from graph.utils import get_project_root
    from graph.runtime import read_result
    preflight()
    if cfg.EXECUTOR_BACKEND == "local":
        (directory / "context.json").write_text(json.dumps(context), encoding="utf-8")
        (directory / "code.py").write_text(code, encoding="utf-8")
        command = [sys.executable, "-X", "utf8", "-m", "graph.runtime",
                   str(directory / "context.json"), str(directory / "code.py")]
        with tempfile.TemporaryDirectory(prefix="da-agent-mpl-") as matplotlib_directory:
            for retry in range(cfg.EXECUTION_TRANSIENT_RETRIES + 1):
                outcome = bounded_process(command, cwd=get_project_root(),
                                          env=local_environment(matplotlib_directory), timeout=timeout)
                if (outcome.returncode == 0 or retry == cfg.EXECUTION_TRANSIENT_RETRIES
                        or not is_transient_bootstrap_error(outcome.stderr)):
                    break
        return outcome, read_result(directory, context["expected_output"]) if outcome.returncode == 0 else None
    job = directory / "job"
    inputs = directory / "inputs"
    job.mkdir()
    inputs.mkdir()
    import pyarrow.parquet as pq
    for name, spec in context["inputs"].items():
        if spec["type"] == "scalar":
            continue
        target = inputs / (name + ".parquet")
        source = pq.ParquetFile(spec["path"])
        schema = source.schema_arrow
        if spec["columns"]:
            import pyarrow as pa
            schema = pa.schema([schema.field(c) for c in spec["columns"]], metadata=schema.metadata)
        with pq.ParquetWriter(target, schema) as writer:
            for batch in source.iter_batches(batch_size=10_000, columns=spec["columns"] or None):
                writer.write_batch(batch)
        spec["path"] = "/inputs/" + target.name
    context["output_dir"] = "/outputs"
    (job / "context.json").write_text(json.dumps(context), encoding="utf-8")
    (job / "code.py").write_text(code, encoding="utf-8")
    (job / "expected.json").write_text(json.dumps(context["expected_output"]), encoding="utf-8")
    with DiskVolume(directory / "volume") as volume:
        mounts = [(job, "/job", True), (inputs, "/inputs", True), (volume, "/outputs", False)]
        outcome = launch(mounts, ["python", "-m", "graph.runtime", "/job/context.json", "/job/code.py"], timeout)
        if outcome.returncode:
            return outcome, None
        validated = launch([(job, "/job", True), (volume, "/outputs", True)],
                           ["python", "-m", "graph.validate_output", "/outputs", "/job/expected.json"], min(timeout, 300))
        if validated.returncode:
            raise ValueError("Sandbox output validation failed: " + validated.stderr[-2000:])
        result = json.loads(validated.stdout)
        # Validator finished and generated code is gone; copy only regular validated files.
        sealed = directory / "sealed"
        sealed.mkdir()
        for source in volume.rglob("*"):
            if source.is_symlink():
                raise ValueError("Output symlink rejected.")
            if source.is_file():
                target = sealed / source.relative_to(volume)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        def translate(path):
            relative = Path(path).relative_to("/outputs")
            return str(sealed / relative)
        if "path" in result:
            result["path"] = translate(result["path"])
        result["artifacts"] = [translate(p) for p in result["artifacts"]]
        result["artifact_hashes"] = {translate(p): value for p, value in result["artifact_hashes"].items()}
        result["directory"] = str(sealed)
        return outcome, result

def register_volume(job_id, path):
    from uuid import UUID
    job_id = str(UUID(job_id))
    import hashlib
    root = Path(cfg.ARTIFACTS_DIR).resolve() / "jobs" / job_id / "volumes"
    root.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    record = root / (identity + ".json")
    temporary = root / (uuid4().hex + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(str(path.resolve())))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, record)

def cleanup_job(job_id):
    from uuid import UUID
    job_id = str(UUID(str(job_id)))
    if cfg.EXECUTOR_BACKEND != "gvisor":
        return
    import fcntl
    root = Path(cfg.ARTIFACTS_DIR).resolve() / "jobs" / job_id
    root.mkdir(parents=True, exist_ok=True)
    with (root / "cleanup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _cleanup_job(job_id)

def _cleanup_job(job_id):
    """Called by the parent on cancellation/crash; never depend on child finally blocks."""
    from uuid import UUID
    job_id = str(UUID(str(job_id)))
    if cfg.EXECUTOR_BACKEND != "gvisor":
        return
    listed = subprocess.run(["docker", "ps", "-aq", "--filter", "label=da-agent.job=" + job_id],
                            capture_output=True, text=True, check=True, timeout=15)
    for container in listed.stdout.splitlines():
        if not re.fullmatch(r"[a-f0-9]{12,64}", container):
            raise ValueError("Unexpected container ID.")
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, check=True, timeout=15)
    root = Path(cfg.ARTIFACTS_DIR).resolve()
    records = root / "jobs" / job_id / "volumes"
    for record in records.glob("*.json"):
        volume = Path(json.loads(record.read_text(encoding="utf-8"))).resolve()
        if not volume.is_relative_to(root) or volume.name != "volume":
            raise ValueError("Invalid orphan volume path.")
        if os.path.ismount(volume):
            subprocess.run(["umount", str(volume)], check=True, timeout=15)
        volume.with_name("volume.ext4").unlink(missing_ok=True)
        if volume.exists():
            volume.rmdir()
        record.unlink(missing_ok=True)
