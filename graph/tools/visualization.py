"""Safe, deterministic chart generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from graph.tools.query import run_query


def create_chart(state: dict[str, Any], sql: str, chart_type: str, x: str | None = None, y: str | None = None, color: str | None = None, title: str | None = None, **_: Any) -> dict[str, Any]:
    allowed = {"bar", "line", "scatter", "histogram", "box", "pie"}
    if chart_type not in allowed:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    query_result = run_query(state, sql=sql, limit=1000)
    df = pd.DataFrame(query_result["rows"])
    if df.empty:
        raise ValueError("Cannot chart an empty result.")
    for column in (x, y, color):
        if column and column not in df.columns:
            raise ValueError(f"Unknown chart column: {column}")
    fig, ax = plt.subplots(figsize=(9, 5))
    if chart_type == "bar":
        if not x or not y: raise ValueError("bar chart requires x and y")
        ax.bar(df[x].astype(str), df[y])
        ax.tick_params(axis="x", rotation=35)
    elif chart_type == "line":
        if not x or not y: raise ValueError("line chart requires x and y")
        ax.plot(df[x], df[y], marker="o")
    elif chart_type == "scatter":
        if not x or not y: raise ValueError("scatter chart requires x and y")
        ax.scatter(df[x], df[y])
    elif chart_type == "histogram":
        if not x: raise ValueError("histogram requires x")
        ax.hist(df[x].dropna(), bins=min(30, max(5, len(df) // 5)))
    elif chart_type == "box":
        if not y: raise ValueError("box chart requires y")
        ax.boxplot(df[y].dropna())
    else:
        if not x or not y: raise ValueError("pie chart requires x and y")
        ax.pie(df[y], labels=df[x].astype(str), autopct="%1.1f%%")
    ax.set_title(title or chart_type.title())
    if x and chart_type not in {"pie", "histogram"}: ax.set_xlabel(x)
    if y and chart_type not in {"pie", "histogram"}: ax.set_ylabel(y)
    fig.tight_layout()
    directory = Path(state.get("artifacts_dir") or "artifacts")
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"chart_{uuid4().hex[:10]}.png"
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return {"ok": True, "artifacts": [str(output).replace("\\", "/")], "chart_type": chart_type, "source_rows": len(df), "truncated": query_result["truncated"]}
