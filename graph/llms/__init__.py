from __future__ import annotations

from typing import TYPE_CHECKING

from configuration import (
    LLM_COMMON_OPTIONS,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_NODE_MAX_OUTPUT_TOKENS,
    LLM_PROVIDER,
    LLM_PROVIDER_OPTIONS,
    LLM_REQUEST_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


def create_llm(
    provider: str = LLM_PROVIDER,
    model: str = LLM_MODEL,
    options: dict | None = None,
) -> BaseChatModel:
    """Create the chat model selected in ``configuration.py``."""
    normalized_provider = provider.strip().lower().replace("-", "_")
    normalized_provider = "self_host" if normalized_provider == "selfhost" else normalized_provider
    runtime_options: dict = {}
    if normalized_provider == "gemini":
        runtime_options = {
            "timeout": LLM_REQUEST_TIMEOUT_SECONDS,
            "max_retries": LLM_MAX_RETRIES,
        }
    elif normalized_provider == "deepseek":
        runtime_options = {
            "request_timeout": LLM_REQUEST_TIMEOUT_SECONDS,
            "max_retries": LLM_MAX_RETRIES,
        }
    elif normalized_provider == "self_host":
        runtime_options = {
            "client_kwargs": {"timeout": LLM_REQUEST_TIMEOUT_SECONDS},
        }

    llm_options = {
        **runtime_options,
        **LLM_COMMON_OPTIONS,
        **LLM_PROVIDER_OPTIONS.get(normalized_provider, {}),
        **(options or {}),
    }

    if normalized_provider == "gemini":
        from graph.llms.gemini import create_gemini_llm

        return create_gemini_llm(model, **llm_options)

    if normalized_provider == "deepseek":
        from graph.llms.deepseek import create_deepseek_llm

        return create_deepseek_llm(model, **llm_options)

    if normalized_provider == "self_host":
        from graph.llms.self_host import create_self_host_llm

        return create_self_host_llm(
            model=model,
            **llm_options,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported providers: gemini, deepseek, self_host."
    )


llm = create_llm()


def get_node_llm(node_name: str):
    """Bind a small, node-specific output budget while reusing one client."""
    try:
        max_output_tokens = LLM_NODE_MAX_OUTPUT_TOKENS[node_name]
    except KeyError as exc:
        raise ValueError(f"Thiếu LLM output budget cho node {node_name!r}.") from exc

    if LLM_PROVIDER == "gemini":
        option_name = "max_output_tokens"
    elif LLM_PROVIDER == "deepseek":
        option_name = "max_tokens"
    else:
        option_name = "num_predict"
    return llm.bind(**{option_name: max_output_tokens})


__all__ = ["create_llm", "get_node_llm", "llm"]
