"""Trusted data loading helpers used by profiling and local tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def safe_alias(value: str, used: set[str] | None = None) -> str:
    import re

    alias = re.sub(r"[^a-zA-Z0-9_]", "_", value).strip("_").lower() or "table"
    if alias[0].isdigit():
        alias = f"t_{alias}"
    if used is None:
        return alias
    base, suffix = alias, 2
    while alias in used:
        alias = f"{base}_{suffix}"
        suffix += 1
    used.add(alias)
    return alias


def load_table(table: dict[str, Any], nrows: int | None = None) -> pd.DataFrame:
    path = Path(table["source_path"])
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, nrows=nrows, low_memory=False)
    if suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=table.get("sheet_name"), nrows=nrows)
    raise ValueError(f"Unsupported file type: {suffix}. Only .csv and .xlsx are supported.")
