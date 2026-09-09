from pathlib import Path

from configuration import (
    ARTIFACTS_DIR,
    HISTORY_MAX_CHARS,
    HISTORY_MAX_MESSAGES,
    USER_INPUT_MAX_CHARS,
    state_override,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def truncate_text(value, max_chars: int, marker: str = "\n...[đã rút gọn]...\n") -> str:
    """Bound text while retaining evidence from both its beginning and end."""
    text = "" if value is None else str(value)
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker):
        return text[:max_chars]
    available = max_chars - len(marker)
    head_chars = available * 3 // 5
    tail_chars = available - head_chars
    return f"{text[:head_chars]}{marker}{text[-tail_chars:]}"


def bounded_messages(messages, max_msgs=None, max_chars=None):
    """Keep the newest chat messages inside both count and character budgets."""
    max_msgs = HISTORY_MAX_MESSAGES if max_msgs is None else max_msgs
    max_chars = HISTORY_MAX_CHARS if max_chars is None else max_chars
    selected = list(messages[-max_msgs:])

    while len(selected) > 1 and sum(
        len(str(message.content)) for message in selected
    ) > max_chars:
        selected.pop(0)

    latest_limit = max_chars
    if selected and selected[-1].type == "human":
        latest_limit = min(latest_limit, USER_INPUT_MAX_CHARS)
    if selected and len(str(selected[-1].content)) > latest_limit:
        selected[-1] = selected[-1].model_copy(
            update={"content": truncate_text(selected[-1].content, latest_limit)}
        )
    return selected


def format_history(messages, max_msgs=None, exclude_last=False) -> str:
    """Nén lịch sử hội thoại thành chuỗi text để nhét vào prompt."""
    msgs = messages[:-1] if exclude_last else messages
    msgs = bounded_messages(msgs, max_msgs=max_msgs)
    lines = [
        f"{'User' if m.type == 'human' else 'AI'}: {m.content}"
        for m in msgs
    ]
    history = "\n".join(lines) if lines else "(bắt đầu hội thoại)"
    return truncate_text(history, HISTORY_MAX_CHARS)


def latest_human_message(messages) -> str:
    """Return the latest user message, even after an AI draft was generated."""
    content = next(
        (message.content for message in reversed(messages) if message.type == "human"),
        "",
    )
    return truncate_text(content, USER_INPUT_MAX_CHARS)


def current_step(state):
    return state["plan"]["steps"][state["current_step_index"]]


def step_inputs(state):
    available = {
        p["dataset_id"]: {"type": "postgres" if p.get("kind") == "postgres" else "dataset",
                          "path": p["path"], "read_options": p["read_options"],
                          **({"broker_source": p["broker_source"]} if p.get("kind") == "postgres" else {})}
        for p in state["profiles"]
    }
    available.update({r["ref"]: r for r in state.get("step_results", [])})
    keys = {"type", "path", "value", "read_options", "broker_source"}
    return {i["source"]: {**{k: v for k, v in available[i["source"]].items() if k in keys}, "columns": i["columns"]}
            for i in current_step(state)["inputs"]}


def analysis_context(state, node="verification"):
    import json
    from configuration import PROMPT_EVIDENCE_MAX_CHARS
    relevant = None
    if node in {"coder", "debugger"}:
        relevant = {item["source"]: item["columns"] for item in current_step(state)["inputs"]}
    evidence = []
    for result in state.get("step_results", []):
        if relevant is not None and result["ref"] not in relevant:
            continue
        keys = {"ref", "type", "columns", "dtypes", "row_count", "value", "preview", "preview_truncated", "checks"}
        if node == "verification":
            keys.add("code")
        evidence.append({key: value for key, value in result.items() if key in keys})
    # Remove whole preview rows; never truncate serialized JSON or executed code.
    import configuration as cfg
    limit = cfg.VERIFICATION_EVIDENCE_MAX_CHARS if node == "verification" else PROMPT_EVIDENCE_MAX_CHARS
    while len(json.dumps(evidence, ensure_ascii=False)) > limit:
        candidate = max((r for r in evidence if r.get("preview")), key=lambda r: len(str(r["preview"])), default=None)
        if candidate is None:
            raise ValueError("Required evidence exceeds context budget; reduce plan size.")
        candidate["preview"] = candidate["preview"][:len(candidate["preview"]) // 2]
        candidate["preview_truncated"] = True
    profiles = []
    if node not in {"synthetic"}:
        for profile in state.get("profiles", []):
            if relevant is not None and profile["dataset_id"] not in relevant:
                continue
            columns = []
            for col in profile["columns"]:
                wanted = relevant.get(profile["dataset_id"], []) if relevant is not None else []
                if wanted and col["name"] not in wanted:
                    continue
                keys = {"name", "suggested_type", "null_count", "mixed_numeric", "leading_zero_count", "datetime", "raw_type"}
                columns.append({k: v for k, v in col.items() if k in keys})
            profiles.append({"dataset_id": profile["dataset_id"], "row_count": profile["row_count"],
                             "kind": profile.get("kind", "file"), "columns": columns})
    return {
        "current_question": latest_human_message(state["messages"]) + (
            "\nResolved request (verify against original and history): " + state["analysis_request"]
            if state.get("analysis_request") and state["analysis_request"] != latest_human_message(state["messages"]) else ""),
        "history": format_history(state["messages"], exclude_last=True),
        "plan": json.dumps(state.get("plan", {}), ensure_ascii=False),
        "profile_summary": json.dumps({"datasets": profiles}, ensure_ascii=False),
        "evidence": json.dumps(evidence, ensure_ascii=False),
        "feedback": state.get("replan_reason") or (state.get("verification") or {}).get("feedback", ""),
    }


def get_project_root() -> Path:
    return PROJECT_ROOT


def resolve_project_path(raw_path: str) -> Path:
    """Đường dẫn tương đối luôn tính từ gốc dự án, kể cả khi đổi cwd."""
    path = Path(raw_path).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve(strict=False)


def get_attempt_artifacts_dir(state) -> Path:
    base = state_override(state, "artifacts_dir", ARTIFACTS_DIR)
    return (resolve_project_path(base) / state["artifact_run_id"]
            / f"plan_{state.get('plan_version', 0)}"
            / f"step_{current_step(state)['step']}"
            / f"attempt_{state.get('debug_count', 0)}")
