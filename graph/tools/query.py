"""Read-only DuckDB data querying tools."""

from __future__ import annotations

import re
from typing import Any

import duckdb

from graph.settings import settings
from graph.tools.data_access import load_table

_BANNED_SQL = re.compile(r"\b(attach|detach|copy|create|insert|update|delete|drop|alter|pragma|install|load|export|import|call|read_csv|read_parquet|read_json|read_xlsx|httpfs)\b", re.I)


def _tables(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {table["alias"]: table for table in state.get("data_profile", {}).get("tables", [])}


def _validate_query(sql: str, aliases: set[str]) -> None:
    if not sql or ";" in sql.strip().rstrip(";"):
        raise ValueError("Only one read-only SQL statement is allowed.")
    if _BANNED_SQL.search(sql):
        raise ValueError("This SQL contains a prohibited operation.")
    try:
        import sqlglot
        from sqlglot import exp
        expression = sqlglot.parse_one(sql, read="duckdb")
        if not isinstance(expression, (exp.Select, exp.Union, exp.Subquery)) and expression.find(exp.Select) is None:
            raise ValueError("Only SELECT/CTE queries are allowed.")
        used = {table.name for table in expression.find_all(exp.Table)}
        unknown = used - aliases
        if unknown:
            raise ValueError(f"Query references tables outside the catalog: {sorted(unknown)}")
    except ImportError as exc:
        raise RuntimeError("sqlglot is required to validate queries.") from exc


def _connection(state: dict[str, Any]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("SET threads = 2")
    for alias, table in _tables(state).items():
        con.register(alias, load_table(table))
    return con


def run_query(state: dict[str, Any], sql: str, limit: int | None = None, **_: Any) -> dict[str, Any]:
    aliases = set(_tables(state))
    _validate_query(sql, aliases)
    limit = max(1, min(int(limit or settings.query_max_rows), settings.query_max_rows))
    con = _connection(state)
    try:
        result = con.execute(f"SELECT * FROM ({sql.rstrip(';')}) AS bounded_result LIMIT {limit + 1}").fetchdf()
    finally:
        con.close()
    truncated = len(result) > limit
    if truncated:
        result = result.iloc[:limit]
    return {"ok": True, "columns": list(result.columns), "rows": result.where(result.notna(), None).to_dict(orient="records"), "returned_rows": len(result), "truncated": truncated}


def aggregate_data(state: dict[str, Any], table: str, metrics: list[dict[str, str]], group_by: list[str] | None = None, limit: int = 100, **_: Any) -> dict[str, Any]:
    table_info = _tables(state).get(table)
    if not table_info:
        raise ValueError(f"Unknown table alias: {table}")
    allowed_columns = {column["name"] for column in table_info.get("column_profiles", [])}
    group_by = group_by or []
    if set(group_by) - allowed_columns:
        raise ValueError("Unknown group_by column.")
    select_parts = [f'"{column}"' for column in group_by]
    for metric in metrics:
        function = metric.get("function", "count").upper()
        column = metric.get("column", "*")
        alias = metric.get("alias") or f"{function.lower()}_{column}"
        if function not in {"COUNT", "SUM", "AVG", "MIN", "MAX", "STDDEV", "MEDIAN"}:
            raise ValueError(f"Unsupported aggregate function: {function}")
        if column != "*" and column not in allowed_columns:
            raise ValueError(f"Unknown metric column: {column}")
        expression = "*" if column == "*" else f'"{column}"'
        select_parts.append(f'{function}({expression}) AS "{alias}"')
    if not select_parts:
        raise ValueError("At least one metric or group_by column is required.")
    group_sql = f" GROUP BY {', '.join(f'\"{column}\"' for column in group_by)}" if group_by else ""
    sql = f'SELECT {", ".join(select_parts)} FROM "{table}"{group_sql}'
    return run_query(state, sql=sql, limit=limit)
