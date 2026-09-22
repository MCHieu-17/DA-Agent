"""LLM provider construction for Gemini and DeepSeek."""

from functools import lru_cache
from typing import TYPE_CHECKING

<<<<<<< HEAD
from configuration import (
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_NODE_MAX_OUTPUT_TOKENS,
    LLM_PROVIDER,
    LLM_REQUEST_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


def create_llm(
    provider: str = LLM_PROVIDER,
    model: str = LLM_MODEL,
    options: dict | None = None,
) -> "BaseChatModel":
    provider = provider.strip().lower()
    options = options or {}
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
=======
from graph.settings import settings
from graph.llms.deepseek import create_deepseek_llm
from graph.llms.gemini import create_gemini_llm
from graph.llms.self_host import create_self_host_llm


def create_llm(
    provider: str = settings.llm_provider,
    model: str = settings.llm_model,
) -> BaseChatModel:
    """Create the chat model selected through environment settings."""
    normalized_provider = provider.strip().lower().replace("-", "_")
>>>>>>> restore-work

        runtime_options = {
            "timeout": LLM_REQUEST_TIMEOUT_SECONDS,
            "max_retries": LLM_MAX_RETRIES,
            **options,
        }
        return ChatGoogleGenerativeAI(model=model, **runtime_options)
    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        runtime_options = {
            "temperature": 0.0,
            "request_timeout": LLM_REQUEST_TIMEOUT_SECONDS,
            "max_retries": LLM_MAX_RETRIES,
            **options,
        }
        return ChatDeepSeek(model=model, **runtime_options)
    raise ValueError(
        f"Unsupported LLM provider {provider!r}; choose 'gemini' or 'deepseek'."
    )


@lru_cache(maxsize=32)
def node_model(node_name: str):
    try:
        limit = LLM_NODE_MAX_OUTPUT_TOKENS[node_name]
    except KeyError as exc:
        raise ValueError(f"Missing LLM output limit for node {node_name!r}.") from exc
    option = "max_output_tokens" if LLM_PROVIDER == "gemini" else "max_tokens"
    return create_llm(options={option: limit})


def get_node_llm(node_name: str):
    return node_model(node_name)


@lru_cache(maxsize=1)
def _shared_llm():
    return create_llm()


def __getattr__(name):
    if name == "llm":
        return _shared_llm()
    raise AttributeError(name)


__all__ = ["create_llm", "get_node_llm", "llm"]
