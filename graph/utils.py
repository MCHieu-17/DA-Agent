from graph.settings import settings


def latest_user_question(messages) -> str:
    return next((str(message.content) for message in reversed(messages) if message.type == "human"), "")


def format_history(messages, max_msgs=None, exclude_last=False) -> str:
    """Nén lịch sử hội thoại thành chuỗi text để nhét vào prompt."""
    msgs = messages[:-1] if exclude_last else messages
    max_msgs = max_msgs or settings.chat_history_max_messages
    lines = [
        f"{'User' if m.type == 'human' else 'AI'}: {m.content}"
        for m in msgs[-max_msgs:]
    ]
    text = "\n".join(lines) if lines else "(bắt đầu hội thoại)"
    return text[-settings.prompt_max_chars:]
