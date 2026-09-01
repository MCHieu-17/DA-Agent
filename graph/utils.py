import os
from pathlib import Path

from configuration import (
    ARTIFACTS_DIR,
    HISTORY_MAX_CHARS,
    HISTORY_MAX_MESSAGES,
    PROMPT_EVIDENCE_MAX_CHARS,
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


def format_step_evidence(past_steps, max_chars=None) -> str:
    """Serialize only the evidence needed by later LLM nodes.

    Generated code and success stderr remain inspectable in state, but are not
    repeatedly sent to planner/coder/synthetic/validator.
    """
    max_chars = PROMPT_EVIDENCE_MAX_CHARS if max_chars is None else max_chars
    chunks = []
    for index, step in enumerate(past_steps, start=1):
        chunks.append(
            "\n".join(
                [
                    f"Bước {index}: {step.get('step', '')}",
                    f"Kết quả: {step.get('stdout', '')}",
                    f"Artifacts: {step.get('artifacts', [])}",
                ]
            )
        )
    evidence = "\n\n".join(chunks) if chunks else "(chưa có bước thành công)"
    return truncate_text(evidence, max_chars)


def get_project_root() -> Path:
    return PROJECT_ROOT


def get_run_artifacts_dir(state) -> str:
    """Return an isolated artifact directory for the current user turn."""
    base_dir = state_override(state, "artifacts_dir", ARTIFACTS_DIR)
    run_id = state.get("artifact_run_id")
    return os.path.join(base_dir, run_id) if run_id else base_dir
