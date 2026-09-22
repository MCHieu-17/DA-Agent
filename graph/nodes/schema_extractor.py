"""Full, cacheable data profiling for CSV and XLSX inputs."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from graph.settings import settings
from graph.state import DataAgentState
from graph.tools.data_access import safe_alias


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: Any) -> float | None:
    if pd.isna(value) or np.isinf(value):
        return None
    return round(float(value), 6)


def _semantic_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series): return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series): return "datetime"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    values = series.dropna()
    if values.empty: return "unknown"
    dates = _parse_dates(values)
    if dates.notna().mean() >= 0.9: return "datetime"
    ratio = values.nunique(dropna=True) / len(values)
    return "id" if ratio > 0.98 else ("categorical" if ratio < 0.2 else "text")


def _parse_dates(values: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(values.astype(str), errors="coerce")


def _column_profile(series: pd.Series, mode: str) -> dict[str, Any]:
    values = series.dropna()
    result: dict[str, Any] = {
        "name": str(series.name), "dtype": str(series.dtype), "semantic_type": _semantic_type(series),
        "null_count": int(series.isna().sum()), "null_rate": round(float(series.isna().mean()), 6),
        "distinct_count": int(values.nunique(dropna=True)), "sample_values": [str(v) for v in values.head(3).tolist()],
    }
    if values.empty: return result
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        result.update({"min": _number(numeric.min()), "max": _number(numeric.max()), "mean": _number(numeric.mean()), "std": _number(numeric.std())})
        if mode == "exact":
            q1, q3 = numeric.quantile([.25, .75])
            iqr = q3 - q1
            result["quantiles"] = {"q25": _number(q1), "q50": _number(numeric.median()), "q75": _number(q3)}
            result["outlier_count"] = int(((numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)).sum())
    elif result["semantic_type"] == "datetime":
        dates = _parse_dates(values).dropna()
        if not dates.empty: result.update({"min": str(dates.min()), "max": str(dates.max())})
    else:
        text = values.astype(str)
        result["top_values"] = [{"value": value, "count": int(count)} for value, count in text.value_counts().head(settings.profile_top_k).items()]
        result["text_length"] = {"min": int(text.str.len().min()), "max": int(text.str.len().max()), "mean": round(float(text.str.len().mean()), 3)}
    return result


def _profile_table(df: pd.DataFrame, alias: str, path: Path, sheet_name: str | None, mode: str, sample_size: int | None) -> dict[str, Any]:
    columns = [_column_profile(df[column], mode) for column in df.columns]
    warnings = []
    if df.empty: warnings.append("empty_table")
    warnings.extend(f"all_null:{item['name']}" for item in columns if len(df) and item["null_count"] == len(df))
    warnings.extend(f"constant:{item['name']}" for item in columns if len(df) and item["distinct_count"] <= 1)
    return {"alias": alias, "name": alias, "source_file": path.name, "source_path": str(path.resolve()), "sheet_name": sheet_name, "rows": int(len(df)), "columns": int(len(df.columns)), "profile_mode": mode, "sample_size": sample_size, "duplicate_count": int(df.duplicated().sum()) if mode == "exact" else None, "possible_keys": [item["name"] for item in columns if len(df) and item["null_count"] == 0 and item["distinct_count"] == len(df)][:5], "warnings": warnings, "column_profiles": columns}


def _read_tables(path: Path) -> list[tuple[str | None, pd.DataFrame]]:
    if path.suffix.lower() == ".csv": return [(None, pd.read_csv(path, low_memory=False))]
    if path.suffix.lower() == ".xlsx":
        workbook = pd.ExcelFile(path)
        return [(sheet, pd.read_excel(workbook, sheet_name=sheet)) for sheet in workbook.sheet_names]
    if path.suffix.lower() == ".xls": raise ValueError("Legacy .xls is not supported; convert it to .xlsx.")
    raise ValueError("Only CSV and XLSX files are supported.")


def _build_profile(file_paths: list[str]) -> dict[str, Any]:
    files, tables, aliases = [], [], set()
    for raw_path in file_paths:
        path = Path(raw_path)
        file_info: dict[str, Any] = {"path": str(path), "name": path.name, "status": "ok"}
        try:
            if not path.exists(): raise FileNotFoundError(path)
            file_info.update({"size_bytes": path.stat().st_size, "fingerprint": _fingerprint(path)})
            for sheet_name, full in _read_tables(path):
                mode = "exact" if len(full) <= settings.profile_exact_row_limit else "hybrid"
                profiled = full if mode == "exact" else full.head(settings.profile_sample_rows)
                alias = safe_alias(f"{path.stem}_{sheet_name}" if sheet_name else path.stem, aliases)
                tables.append(_profile_table(profiled, alias, path, sheet_name, mode, None if mode == "exact" else len(profiled)))
        except Exception as exc:
            file_info.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        files.append(file_info)
    return {"files": files, "tables": tables}


def _summary(profile: dict[str, Any]) -> str:
    lines = ["Data catalog:"]
    for table in profile.get("tables", []):
        columns = ", ".join(f"{item['name']} ({item['semantic_type']})" for item in table["column_profiles"])
        lines.append(f"- {table['alias']}: {table['rows']} rows; {columns}")
    for file_info in profile.get("files", []):
        if file_info.get("status") == "error": lines.append(f"- unreadable {file_info['name']}: {file_info['error']}")
    return "\n".join(lines)


def extract_schema_node(state: DataAgentState):
    paths = state.get("file_paths", [])
    fingerprints = {str(Path(path)): _fingerprint(Path(path)) for path in paths if Path(path).exists()}
    profile = state.get("data_profile") if state.get("data_profile") and fingerprints == state.get("profile_fingerprints", {}) else _build_profile(paths)
    summary = _summary(profile)
    return {"data_profile": profile, "profile_summary": summary, "schema_str": summary, "schema_file_paths": paths, "profile_fingerprints": fingerprints, "plan": [], "current_step_idx": 0, "assumptions": [], "past_steps": [], "execution_records": [], "artifacts": [], "code": None, "execution_status": None, "execution_error": None, "traceback": None, "debug_feedback": None, "retry_count": 0, "tool_retry_count": 0, "replan_count": 0, "max_retries": settings.max_code_retries, "max_replans": settings.max_replans, "is_sufficient": None, "validation_feedback": None, "final_answer": None, "sandbox_id": None, "sandbox_file_map": {}, "run_id": uuid4().hex}
