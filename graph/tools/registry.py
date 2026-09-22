"""Tool catalog and deterministic dispatcher."""

from __future__ import annotations

from typing import Any, Callable

from graph.tools import exploration, query, visualization

Tool = Callable[..., dict[str, Any]]

TOOL_REGISTRY: dict[str, Tool] = {
    "list_tables": exploration.list_tables,
    "describe_table": exploration.describe_table,
    "preview_rows": exploration.preview_rows,
    "get_column_values": exploration.get_column_values,
    "aggregate_data": query.aggregate_data,
    "run_query": query.run_query,
    "create_chart": visualization.create_chart,
}

TOOL_CATALOG = """exploration: list_tables(), describe_table(table, columns?), preview_rows(table, columns?, limit?, offset?), get_column_values(table, column, limit?, search?)
query: aggregate_data(table, metrics, group_by?, limit?), run_query(sql, limit?) [SELECT/CTE only]
visualization: create_chart(sql, chart_type, x?, y?, color?, title?) [bar, line, scatter, histogram, box, pie]"""


def execute_tool(state: dict[str, Any], name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    return tool(state, **arguments)
