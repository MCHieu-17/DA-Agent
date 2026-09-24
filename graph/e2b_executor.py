"""Lifecycle wrapper for generated Python code in an E2B sandbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from graph.settings import settings


def sandbox_file_map(state: dict[str, Any]) -> dict[str, str]:
    return {str(Path(raw_path)): f"/home/user/data/{index}_{Path(raw_path).name}" for index, raw_path in enumerate(state.get("file_paths", []))}


def _sandbox(state: dict[str, Any]):
    try:
        from e2b_code_interpreter import Sandbox
    except ImportError as exc:
        raise RuntimeError("e2b-code-interpreter is not installed.") from exc
    if not os.getenv("E2B_API_KEY"):
        raise RuntimeError("E2B_API_KEY is not configured.")
    sandbox_id = state.get("sandbox_id")
    if sandbox_id:
        return Sandbox.connect(sandbox_id), sandbox_id, state.get("sandbox_file_map", {})
    options: dict[str, Any] = {"timeout": settings.e2b_sandbox_timeout_seconds}
    if settings.e2b_template:
        options["template"] = settings.e2b_template
    # Supported by the current E2B SDK; do not pass host secrets into the sandbox.
    options["allow_internet_access"] = settings.e2b_allow_internet
    sandbox = Sandbox.create(**options)
    sandbox.run_code("import os; os.makedirs('/home/user/data', exist_ok=True); os.makedirs('/home/user/artifacts', exist_ok=True)")
    file_map = sandbox_file_map(state)
    for raw_path, remote in file_map.items():
        path = Path(raw_path)
        sandbox.files.write(remote, path.read_bytes())
    return sandbox, sandbox.sandbox_id, file_map


def _download_artifacts(sandbox: Any, state: dict[str, Any]) -> list[str]:
    listing = sandbox.run_code("import json, os; print(json.dumps([f for f in os.listdir('/home/user/artifacts') if os.path.isfile('/home/user/artifacts/' + f)]))")
    output = "\n".join(getattr(listing.logs, "stdout", []) or [])
    try:
        names = json.loads(output.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        names = []
    target = Path(state.get("artifacts_dir") or settings.default_artifacts_dir) / state.get("run_id", "run")
    target.mkdir(parents=True, exist_ok=True)
    allowed = {".png", ".jpg", ".jpeg", ".csv", ".json", ".html"}
    artifacts = []
    for name in names:
        safe_name = Path(name).name
        if safe_name != name or Path(safe_name).suffix.lower() not in allowed:
            continue
        data = sandbox.files.read(f"/home/user/artifacts/{safe_name}", format="bytes")
        if len(data) > settings.max_artifact_mb * 1024 * 1024:
            continue
        local = target / safe_name
        local.write_bytes(bytes(data))
        artifacts.append(str(local).replace("\\", "/"))
    return artifacts


def execute_code(state: dict[str, Any]) -> dict[str, Any]:
    sandbox, sandbox_id, file_map = _sandbox(state)
    execution = sandbox.run_code(state.get("code", ""))
    logs = getattr(execution, "logs", None)
    stdout = "\n".join(getattr(logs, "stdout", []) or [])
    stderr = "\n".join(getattr(logs, "stderr", []) or [])
    error = getattr(execution, "error", None)
    if error:
        return {"ok": False, "sandbox_id": sandbox_id, "sandbox_file_map": file_map, "stdout": stdout, "stderr": stderr, "error": getattr(error, "name", type(error).__name__), "traceback": getattr(error, "traceback", str(error))}
    return {"ok": True, "sandbox_id": sandbox_id, "sandbox_file_map": file_map, "stdout": stdout, "stderr": stderr, "artifacts": _download_artifacts(sandbox, state)}


def cleanup_sandbox(state: dict[str, Any]) -> None:
    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        return
    try:
        from e2b_code_interpreter import Sandbox
        Sandbox.kill(sandbox_id)
    except Exception:
        # TTL remains a safety net; cleanup must never obscure the user result.
        pass
