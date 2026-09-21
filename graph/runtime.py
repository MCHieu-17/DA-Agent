"""Tiny file-based runtime exposed to LLM-generated Python code."""

import json
import math
from pathlib import Path
import sys

import pandas as pd
import pyarrow.parquet as pq

import configuration as cfg


def read_result(directory, expected):
    """Read and validate the result produced by one local subprocess."""
    directory = Path(directory).resolve()
    manifest_path = directory / "result.json"
    if not manifest_path.is_file():
        raise ValueError("Generated code did not create result.json.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kind = manifest.get("type")
    if kind != expected["type"]:
        raise ValueError(f"Expected {expected['type']}, got {kind}.")

    result = {"type": kind}
    if kind == "scalar":
        value = manifest.get("value")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("Scalar must be a JSON scalar.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Scalar must be finite.")
        result["value"] = value
    else:
        relative = manifest.get("file")
        if not isinstance(relative, str):
            raise ValueError("Result manifest is missing its file.")
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("Result file is missing or outside ARTIFACTS_DIR.")
        result["path"] = str(path)

        if kind == "table":
            parquet = pq.ParquetFile(path)
            names = parquet.schema_arrow.names
            if len(names) != len(set(names)):
                raise ValueError("Output columns must have unique names.")
            missing = set(expected.get("columns", [])) - set(names)
            if missing:
                raise ValueError(f"Missing expected columns: {sorted(missing)}")

            first_batch = next(
                parquet.iter_batches(batch_size=cfg.RESULT_PREVIEW_ROWS), None
            )
            preview = (
                json.loads(
                    first_batch.to_pandas().to_json(
                        orient="records", date_format="iso"
                    )
                )
                if first_batch is not None
                else []
            )
            row_count = parquet.metadata.num_rows
            checks = {}
            expected_rows = expected.get("row_count")
            if expected_rows is not None:
                checks["row_count"] = row_count == expected_rows

            for column in expected.get("non_null_columns", []):
                checks[f"non_null:{column}"] = all(
                    batch.column(0).null_count == 0
                    for batch in parquet.iter_batches(columns=[column])
                )

            unique_columns = expected.get("unique_columns", [])
            if unique_columns:
                keys = pd.read_parquet(path, columns=unique_columns)
                checks["unique"] = not keys.duplicated().any()

            if any(not passed for passed in checks.values()):
                raise ValueError(f"Output assertions failed: {checks}")
            result.update(
                columns=names,
                dtypes={field.name: str(field.type) for field in parquet.schema_arrow},
                row_count=row_count,
                preview=preview,
                preview_truncated=row_count > cfg.RESULT_PREVIEW_ROWS,
                checks=checks,
            )
        elif kind == "chart":
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".html"}:
                raise ValueError("Chart must be PNG, JPG, JPEG, or HTML.")
            if path.stat().st_size == 0:
                raise ValueError("Chart file is empty.")
        else:
            raise ValueError(f"Unsupported result type: {kind!r}.")

    result["artifacts"] = [
        str(path.resolve())
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in cfg.ARTIFACT_ALLOWED_EXTENSIONS
        and path.resolve().is_relative_to(directory)
    ]
    return result


class StepRuntime:
    def __init__(self, context, directory):
        self.context = context
        self.directory = Path(directory).resolve()
        self.result = None

    def load_input(self, source):
        """Load a declared CSV/table source; source CSV values remain strings."""
        if source not in self.context["inputs"]:
            raise ValueError(f"Undeclared input: {source}")
        spec = self.context["inputs"][source]
        columns = spec.get("columns") or None
        if spec["type"] == "dataset":
            return pd.read_csv(
                spec["path"],
                dtype="string",
                usecols=columns,
                **spec["read_options"],
            )
        if spec["type"] == "table":
            return pd.read_parquet(spec["path"], columns=columns, engine="pyarrow")
        if spec["type"] == "scalar":
            return spec["value"]
        raise ValueError("Charts cannot be calculation inputs; use their source table.")

    def _save(self, manifest):
        if self.result is not None:
            raise ValueError("Emit exactly one main result per step.")
        self.result = manifest
        (self.directory / "result.json").write_text(
            json.dumps(manifest, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )

    def save_table(self, frame):
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("save_table expects a pandas DataFrame.")
        frame.to_parquet(self.directory / "result.parquet", engine="pyarrow", index=False)
        self._save({"type": "table", "file": "result.parquet"})

    def save_scalar(self, value):
        if hasattr(value, "item"):
            value = value.item()
        self._save({"type": "scalar", "value": value})

    def save_chart(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.directory):
            raise ValueError("Save charts inside ARTIFACTS_DIR.")
        self._save({"type": "chart", "file": str(path.relative_to(self.directory))})


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m graph.runtime CONTEXT CODE")
    context_path, code_path = map(Path, sys.argv[1:3])
    context = json.loads(context_path.read_text(encoding="utf-8"))
    runtime = StepRuntime(context, code_path.parent)
    namespace = {
        "__name__": "__main__",
        "__file__": str(code_path),
        "ARTIFACTS_DIR": str(runtime.directory),
        "load_input": runtime.load_input,
        "save_table": runtime.save_table,
        "save_scalar": runtime.save_scalar,
        "save_chart": runtime.save_chart,
    }
    code = code_path.read_text(encoding="utf-8")
    exec(compile(code, str(code_path), "exec"), namespace)
    if runtime.result is None:
        raise ValueError("Call save_table, save_scalar, or save_chart exactly once.")


if __name__ == "__main__":
    main()
