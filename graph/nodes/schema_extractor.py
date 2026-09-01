import csv
import hashlib
from pathlib import Path
from uuid import uuid4

import pandas as pd
from configuration import (
    CSV_ALLOWED_EXTENSIONS,
    CSV_HEADER_ENCODING,
    EXECUTION_MAX_TIMEOUT_SECONDS,
    EXECUTION_MIN_TIMEOUT_SECONDS,
    EXECUTION_TIMEOUT_SECONDS,
    MAX_REPLANS,
    MAX_RETRIES,
    SCHEMA_CHUNK_SIZE,
    SCHEMA_CACHE_STRICT_HASH,
    SCHEMA_HASH_ALGORITHM,
    SCHEMA_HASH_BLOCK_BYTES,
    SCHEMA_MAX_CHARS,
    SCHEMA_SAMPLE_ROWS,
    state_override,
)
from graph.state import DataAgentState
from graph.utils import truncate_text


def _file_fingerprints(file_paths: list[str]) -> list[str]:
    """Fingerprint paths by identity and metadata so changed files invalidate cache."""
    fingerprints = []
    for raw_path in file_paths:
        path = Path(raw_path).expanduser().resolve(strict=False)
        try:
            stat = path.stat()
            fingerprint = f"{path}|{stat.st_size}|{stat.st_mtime_ns}"
            if SCHEMA_CACHE_STRICT_HASH:
                digest = hashlib.new(SCHEMA_HASH_ALGORITHM)
                with path.open("rb") as handle:
                    for block in iter(
                        lambda: handle.read(SCHEMA_HASH_BLOCK_BYTES), b""
                    ):
                        digest.update(block)
                fingerprint = f"{fingerprint}|{digest.hexdigest()}"
            fingerprints.append(fingerprint)
        except OSError:
            fingerprints.append(f"{path}|missing")
    return fingerprints


def _build_schema(csv_files: list[str]) -> tuple[str, list[str]]:
    """Validate CSV files and build a schema from all rows in bounded chunks."""
    schema_context = "Dưới đây là thông tin các bảng dữ liệu:\n\n"
    errors: list[str] = []

    if not csv_files:
        errors.append("Chưa có file CSV nào được cung cấp.")

    for raw_path in csv_files:
        file_path = Path(raw_path).expanduser().resolve(strict=False)
        display_path = str(file_path)

        if file_path.suffix.lower() not in CSV_ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(CSV_ALLOWED_EXTENSIONS))
            errors.append(
                f"File không được hỗ trợ (chỉ nhận {allowed}): {display_path}"
            )
            continue
        if not file_path.exists():
            errors.append(f"Không tìm thấy file: {display_path}")
            continue
        if not file_path.is_file():
            errors.append(f"Đường dẫn không phải file: {display_path}")
            continue

        try:
            with file_path.open("r", encoding=CSV_HEADER_ENCODING, newline="") as handle:
                raw_header = next(csv.reader(handle), [])

            if not raw_header:
                raise ValueError("File rỗng hoặc không có header")
            duplicate_columns = sorted(
                {column for column in raw_header if raw_header.count(column) > 1}
            )
            if duplicate_columns:
                errors.append(
                    f"File {display_path} có tên cột trùng: {duplicate_columns}"
                )
            if any(not column.strip() for column in raw_header):
                errors.append(f"File {display_path} có tên cột rỗng.")

            row_count = 0
            null_counts: dict[str, int] = {}
            dtype_candidates: dict[str, set[str]] = {}
            sample_df = None

            for chunk in pd.read_csv(file_path, chunksize=SCHEMA_CHUNK_SIZE):
                if sample_df is None:
                    sample_df = chunk.head(SCHEMA_SAMPLE_ROWS).copy()
                row_count += len(chunk)
                for column in chunk.columns:
                    null_counts[column] = null_counts.get(column, 0) + int(
                        chunk[column].isna().sum()
                    )
                    dtype_candidates.setdefault(column, set()).add(str(chunk[column].dtype))

            if sample_df is None:
                sample_df = pd.read_csv(file_path, nrows=0)

            inferred_types = {
                column: " | ".join(sorted(types))
                for column, types in dtype_candidates.items()
            }
            for column in sample_df.columns:
                inferred_types.setdefault(column, str(sample_df[column].dtype))
                null_counts.setdefault(column, 0)

            schema_context += f"--- Bảng/File: {file_path.name} ---\n"
            schema_context += f"- Đường dẫn CSV chính xác: {display_path}\n"
            schema_context += f"- Số dòng: {row_count}\n"
            schema_context += f"- Cột & kiểu dữ liệu suy luận: {inferred_types}\n"
            schema_context += f"- Số giá trị null theo cột: {null_counts}\n"
            schema_context += f"- Dữ liệu mẫu:\n{sample_df.to_csv(index=False)}\n"
        except Exception as e:
            errors.append(f"Không thể đọc CSV {display_path}: {type(e).__name__}: {e}")

    if errors:
        schema_context += "\nLỖI SCHEMA:\n- " + "\n- ".join(errors) + "\n"
    return truncate_text(schema_context, SCHEMA_MAX_CHARS), errors


def extract_schema_node(state: DataAgentState):
    file_paths = state.get("file_paths", [])
    fingerprints = _file_fingerprints(file_paths)

    # Cache only while both paths and file metadata are unchanged.
    cache_hit = (
        state.get("schema_str") is not None
        and file_paths == state.get("schema_file_paths")
        and fingerprints == state.get("schema_file_fingerprints")
        and state.get("schema_errors") is not None
    )

    if cache_hit:
        schema_str = state["schema_str"]
        schema_errors = state.get("schema_errors", [])
    else:
        schema_str, schema_errors = _build_schema(file_paths)

    # Reset all per-question control/output state, including stale artifacts.
    return {
        "schema_str": schema_str,
        "schema_file_paths": file_paths,
        "schema_file_fingerprints": fingerprints,
        "schema_valid": not schema_errors,
        "schema_errors": schema_errors,
        "plan": [], "past_steps": [], "current_step_idx": 0,
        "code": None, "execution_status": None, "execution_error": None,
        "execution_output": None, "traceback": None, "debug_feedback": None,
        "retry_count": 0, "replan_count": 0,
        "is_sufficient": None, "validation_feedback": None, "final_answer": None,
        "replan_reason": None,
        "artifacts": [],
        "artifact_run_id": uuid4().hex,
        "max_retries": max(
            0, int(state_override(state, "max_retries", MAX_RETRIES))
        ),
        "max_replans": max(
            0, int(state_override(state, "max_replans", MAX_REPLANS))
        ),
        "execution_timeout_seconds": max(
            EXECUTION_MIN_TIMEOUT_SECONDS,
            min(
                int(
                    state_override(
                        state,
                        "execution_timeout_seconds",
                        EXECUTION_TIMEOUT_SECONDS,
                    )
                ),
                EXECUTION_MAX_TIMEOUT_SECONDS,
            ),
        ),
        "workflow_status": "running",
        "failure_reason": None,
        "node_error": None,
    }
