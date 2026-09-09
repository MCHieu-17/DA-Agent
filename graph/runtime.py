"""Small file contract used by generated Python. No LLM imports."""
import hashlib
import json
import math
from pathlib import Path
import sys
import pandas as pd
import configuration as cfg

def read_result(directory, expected):
    """Re-read outputs after exit code zero; derive evidence from actual files."""
    directory = Path(directory).resolve()
    files = []
    for item in directory.rglob("*"):
        if len(files) >= cfg.EXECUTION_MAX_FILES or item.is_symlink():
            raise ValueError("Too many output files or symbolic link detected.")
        files.append(item)
    if sum(p.stat().st_size for p in files if p.is_file()) > cfg.SANDBOX_DISK_MB * 1024 ** 2:
        raise ValueError("Output disk quota exceeded.")
    if (directory / "result.json").stat().st_size > cfg.EXECUTION_MANIFEST_MAX_BYTES:
        raise ValueError("Result manifest too large.")
    manifest = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    kind = manifest["type"]
    if kind != expected["type"]:
        raise ValueError(f"Expected {expected['type']}, got {kind}.")
    result = {"type": kind, "manifest_hash": hashlib.sha256((directory / "result.json").read_bytes()).hexdigest()}
    if kind == "scalar":
        value = manifest["value"]
        if not isinstance(value, (str, int, float, bool, type(None))) or (
            isinstance(value, float) and not math.isfinite(value)
        ):
            raise ValueError("Scalar must be a finite JSON scalar.")
        result["value"] = value
    else:
        path = (directory / manifest["file"]).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("Output file missing or outside this attempt.")
        result["path"] = str(path)
        with path.open("rb") as handle:
            result["content_hash"] = hashlib.file_digest(handle, "sha256").hexdigest()
        if kind == "table":
            import pyarrow.parquet as pq
            parquet = pq.ParquetFile(path)
            names = parquet.schema_arrow.names
            if len(names) != len(set(names)):
                raise ValueError("Output columns must be unique strings.")
            missing = set(expected["columns"]) - set(names)
            if missing:
                raise ValueError(f"Missing expected columns: {sorted(missing)}")
            batch = next(parquet.iter_batches(batch_size=cfg.RESULT_PREVIEW_ROWS), None)
            preview = json.loads(batch.to_pandas().to_json(orient="records", date_format="iso")) if batch is not None else []
            result.update(columns=names, dtypes={f.name: str(f.type) for f in parquet.schema_arrow},
                row_count=parquet.metadata.num_rows, preview=preview,
                preview_truncated=parquet.metadata.num_rows > cfg.RESULT_PREVIEW_ROWS)
            checks = {}
            if expected.get("row_count") is not None:
                checks["row_count"] = parquet.metadata.num_rows == expected["row_count"]
            import pyarrow.compute as pc
            for col in expected.get("non_null_columns", []):
                checks["non_null:" + col] = all(batch.column(0).null_count == 0 for batch in parquet.iter_batches(columns=[col]))
            unique = expected.get("unique_columns", [])
            if unique:
                import duckdb
                with duckdb.connect(config={"memory_limit": "1GB", "threads": 2}) as connection:
                    relation = connection.read_parquet(str(path))
                    columns_sql = ",".join('"' + c.replace('"', '""') + '"' for c in unique)
                    checks["unique"] = relation.project(columns_sql).distinct().count("*").fetchone()[0] == parquet.metadata.num_rows
            if any(not passed for passed in checks.values()):
                raise ValueError(f"Output assertions failed: {checks}")
            result["checks"] = checks
        elif kind == "chart":
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".html"} or path.stat().st_size == 0:
                raise ValueError("Chart must be a nonempty PNG/JPG/HTML.")
    result["artifacts"] = [
        str(p.resolve()) for p in sorted(directory.rglob("*"))
        if p.is_file() and p.suffix.lower() in cfg.ARTIFACT_ALLOWED_EXTENSIONS
        and p.resolve().is_relative_to(directory)
    ]
    result["artifact_hashes"] = {}
    for artifact in result["artifacts"]:
        with Path(artifact).open("rb") as handle:
            result["artifact_hashes"][artifact] = hashlib.file_digest(handle, "sha256").hexdigest()
    return result

class StepRuntime:
    def __init__(self, context, directory):
        self.context = context
        self.directory = Path(directory)
        self.result = None

    def load_input(self, source):
        """Only declared sources; CSV raw strings preserve IDs and ambiguous dates."""
        spec = self.context["inputs"][source]
        columns = spec["columns"]
        if spec.get("path") and Path(spec["path"]).stat().st_size > cfg.PANDAS_MAX_INPUT_BYTES:
            raise ValueError("Input too large for pandas; use input_path/iter_input or a SQL step.")
        if spec.get("path", "").endswith(".parquet"):
            import pyarrow.parquet as pq
            metadata = pq.ParquetFile(spec["path"]).metadata
            if metadata.num_rows > 1_000_000 or sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups)) > cfg.PANDAS_MAX_INPUT_BYTES:
                raise ValueError("Expanded input too large for pandas; use SQL or iter_input.")
        if spec["type"] == "dataset":
            if spec["path"].endswith(".parquet"):
                return pd.read_parquet(spec["path"], columns=columns or None)
            return pd.read_csv(spec["path"], dtype="string", usecols=columns or None,
                               **spec["read_options"])
        if spec["type"] == "table":
            return pd.read_parquet(spec["path"], columns=columns or None, engine="pyarrow")
        if spec["type"] == "scalar":
            return spec["value"]
        raise ValueError("Charts cannot be used as calculation inputs; use their source table.")

    def input_path(self, source):
        return self.context["inputs"][source]["path"]

    def iter_input(self, source):
        import pyarrow.parquet as pq
        spec = self.context["inputs"][source]
        return pq.ParquetFile(spec["path"]).iter_batches(batch_size=10_000, columns=spec["columns"] or None)

    def _save(self, manifest):
        if self.result is not None:
            raise ValueError("Emit exactly one main result per step.")
        self.result = manifest
        (self.directory / "result.json").write_text(
            json.dumps(manifest, ensure_ascii=False, allow_nan=False), encoding="utf-8")

    def save_table(self, frame):
        frame.to_parquet(self.directory / "result.parquet", engine="pyarrow", index=False)
        self._save({"type": "table", "file": "result.parquet"})

    def save_scalar(self, value):
        # Convert numpy scalar without permitting arrays or arbitrary objects.
        if hasattr(value, "item"):
            value = value.item()
        self._save({"type": "scalar", "value": value})

    def save_chart(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.directory.resolve()):
            raise ValueError("Save charts inside ARTIFACTS_DIR.")
        self._save({"type": "chart", "file": str(path.relative_to(self.directory.resolve()))})

def main():
    context_path, code_path = map(Path, sys.argv[1:3])
    context = json.loads(context_path.read_text(encoding="utf-8"))
    runtime = StepRuntime(context, context.get("output_dir", str(code_path.parent)))
    if context.get("engine") == "duckdb_sql":
        execute_sql(runtime, code_path.read_text(encoding="utf-8"), context["expected_output"])
        return
    namespace = {"__name__": "__main__", "__file__": str(code_path),
                 "ARTIFACTS_DIR": str(runtime.directory),
                 "input_path": runtime.input_path, "iter_input": runtime.iter_input,
                 "load_input": runtime.load_input, "save_table": runtime.save_table,
                 "save_scalar": runtime.save_scalar, "save_chart": runtime.save_chart}
    exec(compile(code_path.read_text(encoding="utf-8"), str(code_path), "exec"), namespace)
    if runtime.result is None:
        raise ValueError("Call save_table, save_scalar, or save_chart exactly once.")

def execute_sql(runtime, text, expected):
    import duckdb
    from graph.sql_policy import validate_sql
    validate_sql(text, runtime.context["inputs"])
    conn = duckdb.connect(config={"threads": 2, "memory_limit": "2GB", "temp_directory": str(runtime.directory / "spill"),
                                 "max_temp_directory_size": "18GB", "autoinstall_known_extensions": False,
                                 "autoload_known_extensions": False})
    try:
        for name, spec in runtime.context["inputs"].items():
            if spec["type"] == "scalar":
                conn.register(name, pd.DataFrame({"value": [spec["value"]]}))
            else:
                relation = conn.read_parquet(spec["path"])
                if spec["columns"]:
                    relation = relation.project(",".join('"' + c.replace('"', '""') + '"' for c in spec["columns"]))
                relation.create_view(name)
        result = conn.sql(text)
        if expected["type"] == "scalar":
            rows = result.limit(2).fetchall()
            if len(rows) != 1 or len(rows[0]) != 1:
                raise ValueError("Scalar query must return one row and column.")
            from decimal import Decimal
            value = rows[0][0]
            runtime.save_scalar(str(value) if isinstance(value, Decimal) else value)
        elif expected["type"] == "table":
            result.write_parquet(str(runtime.directory / "result.parquet"))
            runtime._save({"type": "table", "file": "result.parquet"})
        else:
            raise ValueError("SQL cannot produce a chart directly.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
