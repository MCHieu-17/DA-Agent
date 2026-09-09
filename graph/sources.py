"""Registered, authorized sources and immutable projected file snapshots."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import configuration as cfg
from graph.utils import resolve_project_path

def registry():
    return json.loads(Path(cfg.SOURCE_REGISTRY_PATH).read_text(encoding="utf-8"))

def authorized_sources(state):
    refs = state.get("source_refs", [])
    if refs and state.get("file_paths"):
        raise ValueError("Use source_refs or development file_paths, never both.")
    if cfg.ENVIRONMENT == "production" and state.get("file_paths"):
        raise PermissionError("Production requires registered source_refs.")
    if refs:
        catalog = registry()
        result = []
        for ref in refs:
            spec = catalog.get(ref)
            if not spec or state.get("principal") not in spec.get("users", []):
                raise PermissionError("Source access denied.")
            if not spec.get("columns"):
                raise ValueError("Registered sources require an explicit allowed column list.")
            result.append({**spec, "source_ref": ref})
        return result
    return [{"kind": "file", "path": str(resolve_project_path(p)), "columns": None}
            for p in state.get("file_paths", [])]

def source_catalog(state):
    return [{"dataset_id": f"dataset_{i}", "kind": source.get("kind", "file"),
             "name": source.get("source_ref", Path(source.get("path", "")).name),
             "columns": source.get("columns")}
            for i, source in enumerate(authorized_sources(state), 1)]

def snapshot_file(raw_path, columns=None):
    path = resolve_project_path(raw_path)
    if path.suffix.lower() not in {".csv", ".parquet"}:
        raise ValueError("Only CSV and Parquet sources are supported.")
    before = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    identity = hashlib.sha256(json.dumps([digest, columns, cfg.CSV_READ_OPTIONS, 2], sort_keys=True).encode()).hexdigest()
    root = resolve_project_path(cfg.SNAPSHOT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (identity + ".parquet")
    if target.exists():
        return str(target)
    temporary = root / (uuid4().hex + ".tmp")
    writer = None
    try:
        if path.suffix.lower() == ".csv":
            import csv
            with path.open(encoding=cfg.CSV_READ_OPTIONS["encoding"], newline="") as stream:
                header = next(csv.reader(stream, delimiter=cfg.CSV_READ_OPTIONS["sep"]), [])
            if not header or len(header) != len(set(header)) or any(not c.strip() for c in header):
                raise ValueError("Empty or duplicate CSV header.")
            batches = (pa.Table.from_pandas(frame, preserve_index=False) for frame in
                       pd.read_csv(path, dtype="string", usecols=columns,
                                   chunksize=cfg.PROFILE_CHUNK_SIZE, **cfg.CSV_READ_OPTIONS))
        else:
            source = pq.ParquetFile(path)
            batches = (pa.Table.from_batches([batch]) for batch in source.iter_batches(
                batch_size=cfg.PROFILE_CHUNK_SIZE, columns=columns))
        for table in batches:
            if writer is None:
                writer = pq.ParquetWriter(temporary, table.schema)
            writer.write_table(table)
        if writer is None:
            schema = pq.read_schema(path) if path.suffix.lower() == ".parquet" else pa.schema([(c, pa.string()) for c in columns or header])
            pq.write_table(pa.Table.from_batches([], schema=schema), temporary)
        else:
            writer.close()
            writer = None
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Input changed while snapshotting; retry with a stable file.")
        os.replace(temporary, target)
        return str(target)
    finally:
        if writer:
            writer.close()
        temporary.unlink(missing_ok=True)

def prepare_sources(state):
    result = []
    for index, source in enumerate(authorized_sources(state), 1):
        selected = state.get("analysis_columns", {}).get(f"dataset_{index}")
        if selected:
            if source.get("columns") and not set(selected) <= set(source["columns"]):
                raise PermissionError("Selected columns are not authorized.")
            source = {**source, "columns": selected}
        if source.get("kind", "file") == "file":
            result.append({**source, "path": snapshot_file(source["path"], source.get("columns"))})
        elif source["kind"] == "postgres":
            result.append(source)
        else:
            raise ValueError("Unknown source kind.")
    return result
