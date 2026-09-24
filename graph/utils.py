"""Bounded, verified context shared by answer writing and review."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from graph.settings import settings


def latest_user_question(messages) -> str:
    return next((str(m.content) for m in reversed(messages or []) if m.type == "human"), "")


def _shorten(value: Any, limit: int) -> str:
    value = str(value)
    if len(value) <= limit:
        return value
    head = value[:int(limit * 0.7)].rsplit(" ", 1)[0]
    tail = value[-int(limit * 0.2):].split(" ", 1)[-1]
    return f"{head} [lược {len(value) - len(head) - len(tail)} ký tự] {tail}"


def format_history(messages, max_msgs=None, exclude_last=False) -> str:
    msgs = messages[:-1] if exclude_last else messages
    max_msgs = max_msgs or settings.chat_history_max_messages
    lines = [f"{'User' if m.type == 'human' else 'AI'}: {_shorten(m.content, 1800)}" for m in msgs[-max_msgs:]]
    return "\n".join(lines) or "(bắt đầu hội thoại)"


def format_answer_history(answer_history: list[dict[str, str]] | None, max_turns: int = 3) -> str:
    """Only accepted turns can become answer context; trim at turn boundaries."""
    lines = []
    for turn in (answer_history or [])[-max_turns:]:
        if turn.get("question"):
            lines.append(f"User: {_shorten(turn['question'], 1000)}")
        if turn.get("answer"):
            answer = _MARKDOWN_LINK.sub("[artifact của lượt trước]", turn["answer"])
            lines.append(f"AI: {_shorten(answer, 2500)}")
    return "\n".join(lines) or "(bắt đầu hội thoại)"


def related_user_messages(messages, max_messages: int = 5) -> list[str]:
    humans = [str(m.content) for m in messages or [] if m.type == "human"]
    return [_shorten(message, 1000) for message in humans[-(max_messages + 1):-1]]


def _compact_rows(rows: list[Any], shown: int) -> dict[str, Any]:
    selected = rows if len(rows) <= shown else rows[:max(1, shown - 2)] + rows[-2:]
    result: dict[str, Any] = {
        "row_count": len(rows),
        "rows": [_compact_value(row, shown) for row in selected],
    }
    if len(selected) < len(rows):
        result["omitted_rows"] = len(rows) - len(selected)
        numeric: dict[str, list[int | float]] = {}
        for row in rows:
            if isinstance(row, dict):
                for key, value in row.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                        numeric.setdefault(str(key), []).append(value)
        result["numeric_summary_of_all_rows"] = {
            key: {"min": min(values), "max": max(values), "sum": round(sum(values), 8)}
            for key, values in list(numeric.items())[:8]
        }
    return result


def _compact_value(value: Any, shown: int, depth: int = 0) -> Any:
    if depth > 5:
        return "[lược cấu trúc lồng sâu]"
    if isinstance(value, dict):
        return {
            str(key): _compact_rows(item, shown) if key == "rows" and isinstance(item, list)
            else _compact_value(item, shown, depth + 1)
            for key, item in value.items()
            if key not in {"sql", "code", "traceback", "stderr", "artifacts"}
        }
    if isinstance(value, list):
        if len(value) > shown:
            return {"items": [_compact_value(item, shown, depth + 1) for item in value[:shown]], "omitted_items": len(value) - shown}
        return [_compact_value(item, shown, depth + 1) for item in value]
    if isinstance(value, str):
        return _shorten(value, 1800)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def format_evidence(records: list[dict[str, Any]] | None, max_chars: int | None = None, artifact_ids: dict[str, str] | None = None) -> str:
    """Return complete JSON findings, never a suffix of serialized JSON."""
    successful = [record for record in records or [] if record.get("status") == "success"]
    budget = max_chars or settings.prompt_max_chars
    for shown in (24, 12, 5, 2):
        findings = []
        for record in successful:
            result = record.get("result", record.get("summary", ""))
            finding = {
                "objective": record.get("step", ""),
                "kind": record.get("kind", ""),
                "finding": _compact_value(result, shown),
            }
            if artifact_ids:
                ids = [artifact_ids[str(Path(path).resolve())] for path in record.get("artifacts", []) if str(Path(path).resolve()) in artifact_ids]
                if ids:
                    finding["artifact_ids"] = list(dict.fromkeys(ids))
            findings.append(finding)
        document = {"findings": findings}
        rendered = json.dumps(document, ensure_ascii=False, default=str, separators=(",", ":"))
        if len(rendered) <= budget:
            return rendered
    # Preserve the most recent findings whole and explicitly count older omissions.
    while len(findings) > 1:
        findings.pop(0)
        document = {"omitted_older_findings": len(successful) - len(findings), "findings": findings}
        rendered = json.dumps(document, ensure_ascii=False, default=str, separators=(",", ":"))
        if len(rendered) <= budget:
            return rendered
    if findings:
        last = findings[-1]
        compact = {
            "objective": _shorten(last["objective"], 100),
            "kind": last["kind"],
            "detail_omitted": True,
            "key_figures": _key_figures(last["finding"]),
        }
        for count in (12, 6, 2, 0):
            compact["key_figures"] = compact["key_figures"][:count]
            rendered = json.dumps({"omitted_older_findings": len(successful) - 1, "findings": [compact]}, ensure_ascii=False, default=str)
            if len(rendered) <= budget:
                return rendered
    return json.dumps({"omitted_findings": len(successful)}, ensure_ascii=False)


def _key_figures(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    figures = []
    if isinstance(value, dict):
        for key, item in value.items():
            if len(figures) >= 12:
                break
            if key in {"row_count", "returned_rows", "source_rows", "omitted_rows", "omitted_items"}:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                figures.append({"name": path, "value": item})
            elif isinstance(item, dict):
                figures.extend(_key_figures(item, path)[:12 - len(figures)])
            elif isinstance(item, list):
                for index, child in enumerate(item[:3]):
                    figures.extend(_key_figures(child, f"{path}[{index}]")[:12 - len(figures)])
    return figures[:12]


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_ARTIFACT_EXTENSIONS = _IMAGE_EXTENSIONS | {".csv", ".json", ".html", ".pdf", ".xlsx"}
_TOKEN = re.compile(r"\[\[ARTIFACT_(\d+)\]\]")


def artifact_manifest(state: dict[str, Any]) -> list[dict[str, str]]:
    """Only regular files returned by execution may be referenced in the answer."""
    root = Path(state["artifacts_dir"]).resolve() if state.get("artifacts_dir") else None
    manifest, seen = [], set()
    for raw in state.get("artifacts", []) or []:
        if not isinstance(raw, str):
            continue
        path = Path(raw).resolve()
        if path in seen or not path.is_file() or path.suffix.lower() not in _ARTIFACT_EXTENSIONS:
            continue
        if root and not path.is_relative_to(root):
            continue
        seen.add(path)
        manifest.append({"id": f"ARTIFACT_{len(manifest) + 1}", "path": str(path), "kind": "image" if path.suffix.lower() in _IMAGE_EXTENSIONS else "file"})
    return manifest


def resolve_artifact_tokens(answer: str, manifest: list[dict[str, str]]) -> str:
    by_id = {item["id"]: item for item in manifest}

    def replace(match: re.Match[str]) -> str:
        item = by_id.get(f"ARTIFACT_{match.group(1)}")
        if not item:
            return ""  # Never expose an invented artifact code in the public answer.
        path = item["path"].replace(">", "%3E")
        return f"![Biểu đồ](<{path}>)" if item["kind"] == "image" else f"[Tải tệp](<{path}>)"

    return _TOKEN.sub(replace, answer)


_MARKDOWN_LINK = re.compile(r"(?P<image>!?)\[[^\]]*\]\((?:<(?P<angle>[^>]+)>|(?P<plain>[^)]+))\)")


def artifact_reference_issue(answer: str, manifest: list[dict[str, str]]) -> str | None:
    if _TOKEN.search(answer):
        return "Còn mã artifact chưa được giải quyết; dùng mã có trong danh sách artifact hợp lệ."
    valid = {item["path"]: item for item in manifest}
    for match in _MARKDOWN_LINK.finditer(answer):
        target = (match.group("angle") or match.group("plain")).replace("%3E", ">")
        if target.startswith(("https://", "http://", "#")):
            continue
        item = valid.get(target)
        if not item:
            return "Liên kết Markdown trỏ đến artifact không hợp lệ; chỉ dùng artifact trong danh sách."
        if item["kind"] == "image" and not match.group("image"):
            return "Biểu đồ cần được nhúng bằng cú pháp ảnh Markdown cạnh nhận định liên quan."
        if item["kind"] == "file" and match.group("image"):
            return "Tệp tải xuống cần là liên kết Markdown, không phải ảnh."
    prose = _MARKDOWN_LINK.sub("", answer)
    if any(item["path"] in prose for item in manifest):
        return "Đường dẫn artifact xuất hiện trong lời kể; đặt ảnh hoặc liên kết Markdown cạnh nhận định liên quan."
    return None


def evidence_gap(state: dict[str, Any], context: dict[str, Any]) -> str | None:
    """Catch chart gaps that a language-model reviewer can overlook."""
    question = context["user_question"].lower()
    positive_request = re.sub(r"(?:không cần|đừng|without)\s+(?:vẽ\s+|tạo\s+)?(?:biểu đồ|đồ thị|chart|plot)", "", question)
    asks_chart = bool(re.search(r"biểu đồ|đồ thị|chart|plot", positive_request))
    if asks_chart and not any(item["kind"] == "image" for item in context["artifacts"]):
        return "Yêu cầu có biểu đồ nhưng chưa có artifact ảnh hợp lệ; cần tạo hoặc tải lại biểu đồ."
    records = [record for record in (state.get("execution_records") or state.get("past_steps", [])) if record.get("status") == "success"]
    if not records or not all(record.get("kind") == "visualize" for record in records):
        return None
    metadata_only = all(
        isinstance(record.get("result"), dict)
        and not record["result"].get("chart_data")
        and not record["result"].get("rows")
        for record in records
    )
    asks_interpretation = bool(re.search(r"phân tích|cơ cấu|tỷ trọng|so sánh|nhận xét|analy[sz]e|compare|share", question))
    answer_without_links = _MARKDOWN_LINK.sub("", state.get("final_answer", ""))
    claims_numbers = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*%?", answer_without_links))
    if metadata_only and (asks_interpretation or claims_numbers):
        return "Evidence biểu đồ chỉ có metadata, chưa có giá trị đã vẽ để kiểm chứng và diễn giải; cần truy vấn lại số liệu."
    return None


def answer_context(state: dict[str, Any]) -> dict[str, Any]:
    records = state.get("execution_records") or state.get("past_steps", [])
    artifacts = artifact_manifest(state)
    return {
        "user_question": latest_user_question(state.get("messages", [])),
        "related_user_messages": related_user_messages(state.get("messages", [])),
        "conversation_history": format_answer_history(state.get("answer_history")),
        "profile_summary": state.get("profile_summary", ""),
        "assumptions": state.get("assumptions", []),
        "evidence": format_evidence(records, artifact_ids={item["path"]: item["id"] for item in artifacts}),
        "artifacts": artifacts,
    }
