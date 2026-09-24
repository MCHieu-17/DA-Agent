"""Deterministic structural exploration tools."""

from __future__ import annotations

from typing import Any

from graph.tools.data_access import load_table


def _table(state: dict[str, Any], alias: str) -> dict[str, Any]:
    for table in state.get("data_profile", {}).get("tables", []):
        if table["alias"] == alias:
            return table
    raise ValueError(f"Unknown table alias: {alias}")


def list_tables(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    tables = state.get("data_profile", {}).get("tables", [])
    return {"ok": True, "tables": [{k: t.get(k) for k in ("alias", "name", "source_file", "sheet_name", "rows", "columns")} for t in tables]}


def describe_table(state: dict[str, Any], table: str, columns: list[str] | None = None, **_: Any) -> dict[str, Any]:
    profile = _table(state, table)
    result = dict(profile)
    if columns:
        wanted = set(columns)
        result["column_profiles"] = [c for c in profile.get("column_profiles", []) if c["name"] in wanted]
    return {"ok": True, "table": result}


def preview_rows(state: dict[str, Any], table: str, columns: list[str] | None = None, limit: int = 20, offset: int = 0, **_: Any) -> dict[str, Any]:
    df = load_table(_table(state, table))
    if columns:
        unknown = set(columns) - set(df.columns)
        if unknown:
            raise ValueError(f"Unknown columns: {sorted(unknown)}")
        df = df[columns]
    limit = max(1, min(int(limit), 200))
    view = df.iloc[max(0, int(offset)): max(0, int(offset)) + limit]
    return {"ok": True, "columns": list(view.columns), "rows": view.where(view.notna(), None).to_dict(orient="records"), "total_rows": len(df)}


def get_column_values(state: dict[str, Any], table: str, column: str, limit: int = 20, search: str | None = None, **_: Any) -> dict[str, Any]:
    df = load_table(_table(state, table))
    if column not in df.columns:
        raise ValueError(f"Unknown column: {column}")
    values = df[column].dropna().astype(str)
    if search:
        values = values[values.str.contains(search, case=False, regex=False)]
    counts = values.value_counts().head(max(1, min(int(limit), 100)))
    return {"ok": True, "column": column, "values": [{"value": key, "count": int(value)} for key, value in counts.items()]}
