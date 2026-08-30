from langchain_deepseek import ChatDeepSeek


def create_deepseek_llm(model: str) -> ChatDeepSeek:
    """Create a hosted DeepSeek chat model."""
    return ChatDeepSeek(model=model)
