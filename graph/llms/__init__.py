from langchain_core.language_models.chat_models import BaseChatModel

from configuration import (
    LLM_MODEL,
    LLM_PROVIDER,
)
from graph.llms.deepseek import create_deepseek_llm
from graph.llms.gemini import create_gemini_llm
from graph.llms.self_host import create_self_host_llm


def create_llm(
    provider: str = LLM_PROVIDER,
    model: str = LLM_MODEL,
) -> BaseChatModel:
    """Create the chat model selected in ``configuration.py``."""
    normalized_provider = provider.strip().lower().replace("-", "_")

    if normalized_provider == "gemini":
        return create_gemini_llm(model)

    if normalized_provider == "deepseek":
        return create_deepseek_llm(model)

    if normalized_provider in {"self_host", "selfhost"}:
        return create_self_host_llm(
            model=model,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported providers: gemini, deepseek, self_host."
    )


llm = create_llm()

__all__ = ["create_llm", "llm"]
