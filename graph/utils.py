def format_history(messages, max_msgs=6, exclude_last=False) -> str:
    """Nén lịch sử hội thoại thành chuỗi text để nhét vào prompt."""
    msgs = messages[:-1] if exclude_last else messages
    lines = [
        f"{'User' if m.type == 'human' else 'AI'}: {m.content}"
        for m in msgs[-max_msgs:]
    ]
    return "\n".join(lines) if lines else "(bắt đầu hội thoại)"