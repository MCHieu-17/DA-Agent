"""CSV profiling without an LLM. Raw strings are never silently cleaned."""
import csv
import hashlib
import json
import math
from uuid import uuid4
import numpy as np
import pandas as pd
import configuration as cfg
from graph.utils import resolve_project_path

def cache_key(paths):
    settings = {k: getattr(cfg, k) for k in dir(cfg)
                if k.startswith("PROFILE_") or k == "CSV_READ_OPTIONS"}
    parts = []
    for raw in paths:
        path = resolve_project_path(raw)
        try:
            stat = path.stat()
            identity = [str(path), stat.st_size, stat.st_mtime_ns]
            if cfg.PROFILE_CACHE_STRICT_HASH:
                with path.open("rb") as handle:
                    identity.append(hashlib.file_digest(handle, "sha256").hexdigest())
            parts.append(identity)
        except OSError:
            parts.append([str(path), "missing"])
    return hashlib.sha256(json.dumps([parts, settings], sort_keys=True).encode()).hexdigest()

def _chunks(path, usecols=None):
    if str(path).lower().endswith(".parquet"):
        import pyarrow.parquet as pq
        return (batch.to_pandas().astype("string") for batch in pq.ParquetFile(path).iter_batches(
            batch_size=cfg.PROFILE_CHUNK_SIZE, columns=usecols))
    return pd.read_csv(path, dtype="string", chunksize=cfg.PROFILE_CHUNK_SIZE,
                       usecols=usecols, **cfg.CSV_READ_OPTIONS)

def _number_stats():
    return dict(count=0, mean=0.0, m2=0.0, min=None, max=None, zeros=0, negatives=0)

def _accumulate(stats, values):
    values = values[np.isfinite(values)]
    n = len(values)
    if not n:
        return
    mean = float(values.mean())
    m2 = float(((values - mean) ** 2).sum())
    old = stats["count"]
    delta = mean - stats["mean"]
    stats["mean"] += delta * n / (old + n)
    stats["m2"] += m2 + delta * delta * old * n / (old + n)
    stats["count"] += n
    stats["min"] = float(values.min()) if old == 0 else min(stats["min"], float(values.min()))
    stats["max"] = float(values.max()) if old == 0 else max(stats["max"], float(values.max()))
    stats["zeros"] += int((values == 0).sum())
    stats["negatives"] += int((values < 0).sum())

def profile_file(raw_path, dataset_id):
    path = resolve_project_path(raw_path)
    if path.suffix.lower() not in cfg.CSV_ALLOWED_EXTENSIONS | {".parquet"}:
        raise ValueError(f"Unsupported CSV extension: {path}")
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        header = pq.read_schema(path).names
    else:
        with path.open(encoding=cfg.CSV_READ_OPTIONS["encoding"], newline="") as handle:
            header = next(csv.reader(handle, delimiter=cfg.CSV_READ_OPTIONS["sep"]), [])
    if not header or any(not name.strip() for name in header) or len(set(header)) != len(header):
        raise ValueError(f"Empty or duplicate CSV header: {path}")

    columns = {name: {"name": name, "raw_type": "string", "null_count": 0, "non_null_count": 0,
                     "leading_zero_count": 0, "whitespace_count": 0,
                     "min_length": None, "max_length": None} for name in header}
    numbers = {name: _number_stats() for name in header}
    unique_candidates = {name: set() for name in header}
    sample = pd.DataFrame(columns=header)
    priorities = np.array([], dtype=float)
    rng = np.random.default_rng(cfg.PROFILE_SAMPLE_SEED)
    row_count = 0
    for chunk in _chunks(path):
        row_count += len(chunk)
        # Random-priority reservoir: at most sample size + one chunk in memory.
        combined = pd.concat([sample, chunk], ignore_index=True) if len(sample) else chunk.reset_index(drop=True)
        weights = np.concatenate([priorities, rng.random(len(chunk))])
        keep = np.argsort(weights)[:cfg.PROFILE_SAMPLE_ROWS]
        sample = combined.iloc[keep].reset_index(drop=True)
        priorities = weights[keep]
        for name in header:
            values = chunk[name].dropna()
            col = columns[name]
            col["null_count"] += int(chunk[name].isna().sum())
            col["non_null_count"] += len(values)
            col["leading_zero_count"] += int(values.str.match(r"^[+-]?0\d+$").sum())
            col["whitespace_count"] += int(values.ne(values.str.strip()).sum())
            if len(values):
                lengths = values.str.len()
                col["min_length"] = int(lengths.min()) if col["min_length"] is None else min(col["min_length"], int(lengths.min()))
                col["max_length"] = int(lengths.max()) if col["max_length"] is None else max(col["max_length"], int(lengths.max()))
                if len(unique_candidates[name]) < 2:
                    unique_candidates[name].update(values.unique()[:2])
            numeric = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
            _accumulate(numbers[name], numeric)

    for name, col in columns.items():
        stats = numbers[name]
        count = col["non_null_count"]
        col["null_rate"] = col["null_count"] / row_count if row_count else None
        col["constant"] = count > 0 and len(unique_candidates[name]) == 1
        col["suggested_type"] = (
            "unknown" if count == 0 else
            "string" if col["leading_zero_count"] else
            "numeric" if stats["count"] == count else "string"
        )
        col["mixed_numeric"] = 0 < stats["count"] < count
        col["numeric"] = {
            "scope": "full_file_finite_numeric_values",
            **{k: v for k, v in stats.items() if k not in {"m2", "mean"}},
            "mean": stats["mean"] if stats["count"] else None,
            "std": math.sqrt(max(0, stats["m2"] / (stats["count"] - 1))) if stats["count"] > 1 else None,
            "parse_rate": stats["count"] / count if count else None,
        }
        vals = sample[name].dropna()
        numeric_sample = pd.to_numeric(vals, errors="coerce").dropna().astype(float)
        numeric_sample = numeric_sample[np.isfinite(numeric_sample)]
        quantiles = numeric_sample.quantile([.25, .5, .75]).tolist() if len(numeric_sample) else []
        outliers = 0
        if quantiles:
            q1, _, q3 = quantiles
            outliers = int(((numeric_sample < q1 - 1.5*(q3-q1)) | (numeric_sample > q3 + 1.5*(q3-q1))).sum())
        col["sample"] = {
            "scope": "sample", "rows": len(sample), "non_null_count": len(vals),
            "distinct_count": int(vals.nunique()),
            "examples": [str(x)[:120] for x in vals.head(cfg.PROFILE_EXAMPLE_ROWS)],
            "top_values": [{"value": str(v)[:120], "count": int(n)}
                           for v, n in vals.value_counts().head(cfg.PROFILE_TOP_K).items()],
            "quartiles_numeric": quantiles,
            "iqr_outlier_count_numeric": outliers,
        }
    native_dates = set()
    if path.suffix.lower() == ".parquet":
        import pyarrow as pa
        for field in pq.read_schema(path):
            columns[field.name]["raw_type"] = str(field.type)
            if pa.types.is_timestamp(field.type) or pa.types.is_date(field.type):
                native_dates.add(field.name)
                columns[field.name]["suggested_type"] = "datetime"
                columns[field.name]["datetime"] = {"scope": "schema", "format": None,
                                                    "ambiguous": False, "native": True}
    # Date candidates come from the reservoir; candidate formats are then checked over ALL rows.
    candidates = [name for name in header if name not in native_dates and len(sample[name].dropna()) and
                  sample[name].dropna().str.match(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}(?:[ T].*)?$").mean() >= .8]
    date_stats = {name: {fmt: {"count": 0, "min": None, "max": None, "digest": hashlib.sha256()}
                         for fmt in cfg.PROFILE_DATE_FORMATS} for name in candidates}
    if candidates:
        for chunk in _chunks(path, candidates):
            for name in candidates:
                for fmt, stats in date_stats[name].items():
                    parsed = pd.to_datetime(chunk[name], format=fmt, errors="coerce")
                    valid = parsed.dropna()
                    stats["count"] += len(valid)
                    stats["digest"].update(pd.util.hash_pandas_object(parsed, index=False).values.tobytes())
                    if len(valid):
                        stats["min"] = valid.min() if stats["min"] is None else min(stats["min"], valid.min())
                        stats["max"] = valid.max() if stats["max"] is None else max(stats["max"], valid.max())
        for name, formats in date_stats.items():
            best_count = max(s["count"] for s in formats.values())
            best = [fmt for fmt, stats in formats.items() if stats["count"] == best_count and best_count]
            ambiguous = len({formats[f]["digest"].hexdigest() for f in best}) > 1
            chosen = best[0] if best and not ambiguous else None
            columns[name]["datetime"] = {
                "scope": "full_file", "format": chosen, "ambiguous": ambiguous,
                "formats": {f: {"parsed_count": s["count"],
                                "parse_rate": s["count"] / columns[name]["non_null_count"]}
                            for f, s in formats.items()},
                "min": formats[chosen]["min"].isoformat() if chosen else None,
                "max": formats[chosen]["max"].isoformat() if chosen else None,
            }
            if chosen and best_count == columns[name]["non_null_count"]:
                columns[name]["suggested_type"] = "datetime"
    warnings = []
    for name, col in columns.items():
        if col["null_count"]:
            warnings.append(f"{name}: {col['null_count']} missing values.")
        if col["mixed_numeric"]:
            warnings.append(f"{name}: mixed numeric and non-numeric values.")
        if col.get("datetime", {}).get("ambiguous"):
            warnings.append(f"{name}: ambiguous date format; clarify before date calculations.")
    return {"dataset_id": dataset_id, "path": str(path), "read_options": dict(cfg.CSV_READ_OPTIONS),
            "row_count": row_count, "column_count": len(header), "columns": list(columns.values()),
            "warnings": warnings, "sample": {"scope": "sample", "rows": len(sample),
            "seed": cfg.PROFILE_SAMPLE_SEED, "duplicate_rows": int(sample.duplicated().sum())}}

def summarize_profiles(profiles):
    # Drop entire optional fields, never slice serialized JSON.
    compact = json.loads(json.dumps(profiles, allow_nan=False))
    def encode():
        return json.dumps({"datasets": compact, "omitted_details": omitted}, ensure_ascii=False, allow_nan=False)
    omitted = False
    for field in ("sample", "numeric", "datetime"):
        if len(encode()) <= cfg.PROFILE_MAX_CHARS:
            return encode()
        omitted = True
        for dataset in compact:
            for col in dataset["columns"]:
                if field == "datetime" and field in col:
                    col[field] = {k: col[field][k] for k in ("format", "ambiguous")}
                else:
                    col.pop(field, None)
            dataset.pop("sample", None)
    if len(encode()) > cfg.PROFILE_MAX_CHARS:
        for dataset in compact:
            dataset["columns"] = [{k: col[k] for k in ("name", "suggested_type", "null_count", "datetime") if k in col}
                                  for col in dataset["columns"]]
    if len(encode()) > cfg.PROFILE_MAX_CHARS:
        raise ValueError("Too many columns for the profile context; select fewer CSV files/columns.")
    return encode()

def data_profiling_node(state):
    from graph.sources import prepare_sources
    try:
        sources = prepare_sources(state)
    except Exception as exc:
        sources = []
        source_error = type(exc).__name__ if cfg.ENVIRONMENT == "production" else f"{type(exc).__name__}: {exc}"
    else:
        source_error = None
    paths = [s["path"] for s in sources if s.get("kind", "file") == "file"]
    key = cache_key(paths)
    if not source_error and len(paths) == len(sources) and state.get("profile_cache_key") == key and "profiles" in state:
        profiles, errors = state["profiles"], list(state.get("profile_errors", []))
    else:
        profiles, errors = [], []
        if source_error:
            errors.append(source_error)
        if not sources:
            errors.append("Chưa có file CSV. Hãy cung cấp đường dẫn dữ liệu.")
        for i, source in enumerate(sources, 1):
            try:
                if source.get("kind", "file") == "postgres":
                    from graph.postgres import profile
                    profiles.append(profile(source, f"dataset_{i}"))
                else:
                    profiles.append(cached_profile(source["path"], f"dataset_{i}"))
            except Exception as exc:
                errors.append(f"dataset_{i}: {type(exc).__name__}" + (f": {exc}" if cfg.ENVIRONMENT != "production" else ""))
    try:
        summary = summarize_profiles(profiles)
    except ValueError as exc:
        summary = "{}"
        errors.append(str(exc))
    if any(p["row_count"] == 0 for p in profiles):
        errors.append("CSV không có dòng dữ liệu.")
    errors = list(dict.fromkeys(errors))
    return {
        "profiles": profiles, "profile_summary": summary, "profile_cache_key": key,
        "profile_errors": errors, "profile_valid": not errors,
        "plan": {}, "plan_version": 0, "current_step_index": 0, "step_results": [],
        "plan_history": [], "attempt_history": [], "code": None,
        "execution_status": None, "execution_output": None, "execution_error": None,
        "traceback": None, "debug_count": 0, "replan_count": 0,
        "answer_revision_count": 0, "replan_reason": None, "verification": None,
        "draft_answer": None, "clarification_question": None, "artifacts": [],
        "artifact_run_id": state.get("artifact_run_id", uuid4().hex) if state.get("schema_version") == 2 else uuid4().hex,
        "final_answer": None, "workflow_status": "running",
        "node_error": None, "termination_reason": None,
        "execution_timeout_seconds": max(cfg.EXECUTION_MIN_TIMEOUT_SECONDS, min(
            int(cfg.state_override(state, "execution_timeout_seconds", cfg.EXECUTION_TIMEOUT_SECONDS)),
            cfg.EXECUTION_MAX_TIMEOUT_SECONDS)),
    }

def cached_profile(path, dataset_id):
    """Immutable snapshot + profiling configuration = persistent reusable profile."""
    key = cache_key([path])
    root = resolve_project_path(cfg.SNAPSHOT_DIR) / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    target = root / (key + ".json")
    if target.exists():
        value = json.loads(target.read_text(encoding="utf-8"))
        return {**value, "dataset_id": dataset_id}
    value = profile_file(path, dataset_id)
    temporary = root / (uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
    import os
    os.replace(temporary, target)
    return value
