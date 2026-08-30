from langchain_ollama import ChatOllama


def create_self_host_llm(
    model: str,
) -> ChatOllama:
    """Create a chat model served locally by Ollama."""
    return ChatOllama(
        model=model,
    )
