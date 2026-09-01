import ast
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from configuration import (
    ARTIFACT_ALLOWED_EXTENSIONS,
    ARTIFACT_MAX_FILES,
    ARTIFACT_TOTAL_LIMIT_MB,
    EXECUTION_ALLOWED_IMPORTS,
    EXECUTION_BLOCKED_CALLS,
    EXECUTION_CPU_GRACE_SECONDS,
    EXECUTION_ERROR_MAX_CHARS,
    EXECUTION_FILE_SIZE_LIMIT_MB,
    EXECUTION_ISOLATED_PYTHON,
    EXECUTION_LOCALE,
    EXECUTION_MATPLOTLIB_BACKEND,
    EXECUTION_MAX_OPEN_FILES,
    EXECUTION_MAX_PROCESSES,
    EXECUTION_MAX_TIMEOUT_SECONDS,
    EXECUTION_MEMORY_LIMIT_MB,
    EXECUTION_MIN_TIMEOUT_SECONDS,
    EXECUTION_THREAD_LIMIT,
    EXECUTION_TEMP_DIR,
    EXECUTION_TIMEOUT_SECONDS,
    EXECUTION_STDERR_MAX_BYTES,
    EXECUTION_STDOUT_MAX_BYTES,
    EXECUTION_WRITE_METHODS,
)
from graph.state import DataAgentState
from graph.utils import get_project_root, get_run_artifacts_dir


def _resolved(path: str | os.PathLike) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


class _SafetyVisitor(ast.NodeVisitor):
    """Reject common escape hatches before running generated analysis code."""

    def __init__(self, allowed_files: set[Path], artifacts_dir: Path):
        self.allowed_files = allowed_files
        self.artifacts_dir = artifacts_dir
        self.string_constants: dict[str, str] = {
            "ARTIFACTS_DIR": str(artifacts_dir)
        }

    def visit_Assign(self, node: ast.Assign):
        string_value = self._string_argument(node.value)
        if string_value is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.string_constants[target.id] = string_value
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.split(".", 1)[0] not in EXECUTION_ALLOWED_IMPORTS:
                raise ValueError(f"Import không được phép: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module_root = (node.module or "").split(".", 1)[0]
        if node.level or module_root not in EXECUTION_ALLOWED_IMPORTS:
            raise ValueError(f"Import không được phép: {node.module}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__"):
            raise ValueError(f"Truy cập thuộc tính đặc biệt không được phép: {node.attr}")
        self.generic_visit(node)

    def _string_argument(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.string_constants.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._string_argument(node.left)
            right = self._string_argument(node.right)
            return f"{left}{right}" if left is not None and right is not None else None
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue):
                    formatted = self._string_argument(value.value)
                    if formatted is None:
                        return None
                    parts.append(formatted)
                else:
                    return None
            return "".join(parts)
        return None

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in EXECUTION_BLOCKED_CALLS:
            raise ValueError(f"Hàm không được phép: {node.func.id}")

        if isinstance(node.func, ast.Attribute) and node.func.attr == "read_csv":
            path_node = node.args[0] if node.args else next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "filepath_or_buffer"
                ),
                None,
            )
            if path_node is None:
                raise ValueError("read_csv phải nhận đường dẫn CSV được cung cấp.")
            raw_path = self._string_argument(path_node)
            if raw_path is None or _resolved(raw_path) not in self.allowed_files:
                raise ValueError("read_csv chỉ được đọc các file CSV đã cung cấp.")

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in EXECUTION_WRITE_METHODS
        ):
            path_node = node.args[0] if node.args else next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg
                    in {"file", "file_name", "fname", "path", "path_or_buf"}
                ),
                None,
            )
            # ``to_csv()`` without a path returns text and does not write a file.
            if path_node is not None:
                raw_path = self._string_argument(path_node)
                if raw_path is None or not _is_within(
                    _resolved(raw_path), self.artifacts_dir
                ):
                    raise ValueError(
                        f"{node.func.attr} chỉ được ghi vào thư mục artifacts của lượt chạy."
                    )

        self.generic_visit(node)


def _validate_generated_code(
    code: str,
    allowed_files: set[Path],
    artifacts_dir: Path,
) -> None:
    if not code.strip():
        raise ValueError("Coder trả về code rỗng.")
    tree = ast.parse(code, mode="exec")
    _SafetyVisitor(allowed_files, artifacts_dir).visit(tree)


def _snapshot_artifacts(directory: Path) -> dict[Path, tuple[int, int]]:
    snapshot = {}
    for path in directory.rglob("*"):
        if path.is_file():
            stat = path.stat()
            snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _limit_child_resources(timeout_seconds: int):
    """Apply Linux resource limits in the generated-code subprocess."""
    import resource

    resource.setrlimit(
        resource.RLIMIT_CPU,
        (timeout_seconds, timeout_seconds + EXECUTION_CPU_GRACE_SECONDS),
    )
    memory_limit = EXECUTION_MEMORY_LIMIT_MB * 1024**2
    file_size_limit = EXECUTION_FILE_SIZE_LIMIT_MB * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_limit, file_size_limit))
    resource.setrlimit(
        resource.RLIMIT_NOFILE,
        (EXECUTION_MAX_OPEN_FILES, EXECUTION_MAX_OPEN_FILES),
    )
    if EXECUTION_MAX_PROCESSES is not None and hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(
            resource.RLIMIT_NPROC,
            (EXECUTION_MAX_PROCESSES, EXECUTION_MAX_PROCESSES),
        )


class _OutputLimitExceeded(RuntimeError):
    def __init__(self, stream_name: str, limit_bytes: int):
        self.stream_name = stream_name
        self.limit_bytes = limit_bytes
        super().__init__(
            f"{stream_name} vượt quá giới hạn {limit_bytes} bytes; child đã bị dừng."
        )


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Terminate the isolated child session and any descendants it created."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_bounded_subprocess(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess:
    """Capture child output incrementally so pipe data cannot exhaust RAM."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        preexec_fn=lambda: _limit_child_resources(timeout_seconds),
    )
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    assert process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {
        "stdout": EXECUTION_STDOUT_MAX_BYTES,
        "stderr": EXECUTION_STDERR_MAX_BYTES,
    }
    deadline = time.monotonic() + timeout_seconds

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(
                    command,
                    timeout_seconds,
                    output=bytes(buffers["stdout"]),
                    stderr=bytes(buffers["stderr"]),
                )

            for key, _ in selector.select(timeout=min(0.1, remaining)):
                stream_name = key.data
                chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[stream_name].extend(chunk)
                if len(buffers[stream_name]) > limits[stream_name]:
                    raise _OutputLimitExceeded(
                        stream_name, limits[stream_name]
                    )

        remaining = max(0.0, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            exc.output = bytes(buffers["stdout"])
            exc.stderr = bytes(buffers["stderr"])
            raise
    except Exception:
        _terminate_process_tree(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    return subprocess.CompletedProcess(
        command,
        returncode,
        bytes(buffers["stdout"]).decode("utf-8", errors="replace"),
        bytes(buffers["stderr"]).decode("utf-8", errors="replace"),
    )


def _error_update(state: DataAgentState, error_type: str, detail: str) -> dict:
    return {
        "execution_status": "error",
        "execution_error": error_type,
        "traceback": detail[-EXECUTION_ERROR_MAX_CHARS:],
        # retry_count is incremented by debugger when a retry is actually scheduled.
        "retry_count": state.get("retry_count", 0),
    }


def _local_execution_node(state: DataAgentState):
    code = state.get("code", "") or ""
    current_idx = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    project_dir = get_project_root()
    raw_artifacts_dir = Path(get_run_artifacts_dir(state)).expanduser()
    artifacts_dir = (
        raw_artifacts_dir
        if raw_artifacts_dir.is_absolute()
        else project_dir / raw_artifacts_dir
    ).resolve(strict=False)
    timeout_seconds = max(
        EXECUTION_MIN_TIMEOUT_SECONDS,
        min(
            state.get("execution_timeout_seconds", EXECUTION_TIMEOUT_SECONDS),
            EXECUTION_MAX_TIMEOUT_SECONDS,
        ),
    )
    allowed_files = {_resolved(path) for path in state.get("file_paths", [])}

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    files_before = _snapshot_artifacts(artifacts_dir)

    try:
        _validate_generated_code(code, allowed_files, artifacts_dir)
    except (SyntaxError, ValueError) as exc:
        return _error_update(state, type(exc).__name__, str(exc))

    bootstrap = f"ARTIFACTS_DIR = {str(artifacts_dir)!r}\n"
    child_env = {
        "LANG": EXECUTION_LOCALE,
        "LC_ALL": EXECUTION_LOCALE,
        "MPLBACKEND": EXECUTION_MATPLOTLIB_BACKEND,
        "OPENBLAS_NUM_THREADS": str(EXECUTION_THREAD_LIMIT),
        "OMP_NUM_THREADS": str(EXECUTION_THREAD_LIMIT),
        "OMP_THREAD_LIMIT": str(EXECUTION_THREAD_LIMIT),
        "OMP_DYNAMIC": "FALSE",
        "MKL_NUM_THREADS": str(EXECUTION_THREAD_LIMIT),
        "MKL_DYNAMIC": "FALSE",
        "NUMEXPR_NUM_THREADS": str(EXECUTION_THREAD_LIMIT),
        "NUMEXPR_MAX_THREADS": str(EXECUTION_THREAD_LIMIT),
        "VECLIB_MAXIMUM_THREADS": str(EXECUTION_THREAD_LIMIT),
        "BLIS_NUM_THREADS": str(EXECUTION_THREAD_LIMIT),
    }

    try:
        with tempfile.TemporaryDirectory(
            prefix="da-agent-mpl-", dir=EXECUTION_TEMP_DIR
        ) as mpl_dir:
            child_env["MPLCONFIGDIR"] = mpl_dir
            completed = _run_bounded_subprocess(
                [
                    sys.executable,
                    *(["-I"] if EXECUTION_ISOLATED_PYTHON else []),
                    "-c",
                    bootstrap + code,
                ],
                cwd=project_dir,
                env=child_env,
                timeout_seconds=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        return _error_update(
            state,
            "TimeoutExpired",
            f"Code chạy quá giới hạn {timeout_seconds} giây. stdout={exc.stdout!r}; stderr={exc.stderr!r}",
        )
    except _OutputLimitExceeded as exc:
        return _error_update(state, "OutputLimitExceeded", str(exc))
    except Exception as exc:
        return _error_update(state, type(exc).__name__, str(exc))

    if completed.returncode != 0:
        if completed.returncode == -signal.SIGXCPU:
            return _error_update(
                state,
                "TimeoutExpired",
                f"Code vượt quá giới hạn CPU {timeout_seconds} giây.",
            )
        detail = completed.stderr or f"Process kết thúc với mã {completed.returncode}."
        return _error_update(state, "SubprocessError", detail)

    files_after = _snapshot_artifacts(artifacts_dir)
    changed_files = sorted(
        path
        for path, fingerprint in files_after.items()
        if files_before.get(path) != fingerprint
    )
    changed_bytes = sum(files_after[path][1] for path in changed_files)
    artifact_total_limit_bytes = ARTIFACT_TOTAL_LIMIT_MB * 1024**2
    if (
        len(changed_files) > ARTIFACT_MAX_FILES
        or changed_bytes > artifact_total_limit_bytes
    ):
        for path in changed_files:
            if path not in files_before:
                try:
                    path.unlink()
                except OSError:
                    pass
        return _error_update(
            state,
            "ArtifactLimitExceeded",
            "Artifact vượt quota: "
            f"files={len(changed_files)}/{ARTIFACT_MAX_FILES}, "
            f"bytes={changed_bytes}/{artifact_total_limit_bytes}.",
        )
    artifacts = []
    for path in changed_files:
        if path.suffix.lower() not in ARTIFACT_ALLOWED_EXTENSIONS:
            continue
        if raw_artifacts_dir.is_absolute():
            artifacts.append(str(path))
        else:
            artifacts.append(str(path.relative_to(project_dir)))
    stdout_str = completed.stdout.strip()

    if not stdout_str and not artifacts:
        return _error_update(
            state,
            "MissingExecutionOutput",
            "Code chạy xong nhưng không print kết quả và không tạo artifact.",
        )

    step_result = {
        "step": current_step,
        "code": code,
        "stdout": stdout_str,
        "stderr": completed.stderr.strip(),
        "artifacts": artifacts,
    }
    return {
        "execution_status": "success",
        "execution_output": stdout_str,
        "execution_error": None,
        "traceback": None,
        "past_steps": state.get("past_steps", []) + [step_result],
        "current_step_idx": current_idx + 1,
        "retry_count": 0,
        "artifacts": state.get("artifacts", []) + artifacts,
    }


def _container_execution_node(state: DataAgentState) -> dict:
    """Delegate generated code to the private sandbox controller.

    Only a service run identifier and generated code cross this boundary. The
    controller resolves dataset objects from PostgreSQL; callers cannot submit
    host paths or artifact destinations.
    """
    import httpx

    from da_agent_service.settings import get_settings

    settings = get_settings()
    code = state.get("code", "") or ""
    current_idx = state.get("current_step_idx", 0)
    plan = state.get("plan", [])
    current_step = plan[current_idx] if current_idx < len(plan) else "No step"
    virtual_files = {
        _resolved(path) for path in state.get("execution_file_paths", [])
    }
    virtual_output = _resolved(
        state.get("execution_artifacts_dir", "/workspace/output")
    )
    try:
        _validate_generated_code(code, virtual_files, virtual_output)
    except (SyntaxError, ValueError) as exc:
        return _error_update(state, type(exc).__name__, str(exc))

    service_run_id = state.get("service_run_id")
    if not service_run_id:
        return _error_update(
            state, "MissingRunContext", "Container execution requires a service run id."
        )
    timeout_seconds = max(
        EXECUTION_MIN_TIMEOUT_SECONDS,
        min(
            state.get("execution_timeout_seconds", EXECUTION_TIMEOUT_SECONDS),
            EXECUTION_MAX_TIMEOUT_SECONDS,
        ),
    )
    execution_id = "-".join(
        [
            service_run_id,
            str(current_idx),
            str(state.get("retry_count", 0)),
            str(state.get("replan_count", 0)),
            uuid.uuid4().hex[:8],
        ]
    )
    try:
        response = httpx.post(
            f"{settings.sandbox_controller_url.rstrip('/')}/internal/v1/execute",
            headers={"X-Internal-Token": settings.internal_service_token},
            json={
                "run_id": service_run_id,
                "code": code,
                "execution_id": execution_id,
                "timeout_seconds": timeout_seconds,
            },
            timeout=timeout_seconds + 15,
        )
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        return _error_update(
            state,
            "SandboxControllerError",
            f"Sandbox controller unavailable: {type(exc).__name__}",
        )

    if result.get("status") != "success":
        return _error_update(
            state,
            result.get("error_type") or "SandboxExecutionError",
            result.get("error_detail") or "Sandbox execution failed.",
        )
    artifacts = [str(value) for value in result.get("artifacts", [])]
    stdout = str(result.get("stdout", "")).strip()
    if not stdout and not artifacts:
        return _error_update(
            state,
            "MissingExecutionOutput",
            "Code completed without stdout or an artifact.",
        )
    step_result = {
        "step": current_step,
        "code": code,
        "stdout": stdout,
        "stderr": str(result.get("stderr", "")).strip(),
        "artifacts": artifacts,
    }
    return {
        "execution_status": "success",
        "execution_output": stdout,
        "execution_error": None,
        "traceback": None,
        "past_steps": state.get("past_steps", []) + [step_result],
        "current_step_idx": current_idx + 1,
        "retry_count": 0,
        "artifacts": state.get("artifacts", []) + artifacts,
    }


def execution_node(state: DataAgentState):
    backend = os.getenv("DA_EXECUTION_BACKEND", "local").strip().lower()
    if backend == "container":
        return _container_execution_node(state)
    return _local_execution_node(state)
