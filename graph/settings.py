"""Typed runtime settings loaded exclusively from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    chat_history_max_messages: int = _int("CHAT_HISTORY_MAX_MESSAGES", 6)
    prompt_max_chars: int = _int("PROMPT_MAX_CHARS", 12000)
    profile_exact_row_limit: int = _int("PROFILE_EXACT_ROW_LIMIT", 100000)
    profile_sample_rows: int = _int("PROFILE_SAMPLE_ROWS", 5000)
    profile_top_k: int = _int("PROFILE_TOP_K", 8)
    query_max_rows: int = _int("QUERY_MAX_ROWS", 200)
    query_timeout_seconds: int = _int("QUERY_TIMEOUT_SECONDS", 30)
    max_tool_retries: int = _int("MAX_TOOL_RETRIES", 2)
    max_code_retries: int = _int("MAX_CODE_RETRIES", 2)
    max_replans: int = _int("MAX_REPLANS", 2)
    default_artifacts_dir: str = os.getenv("DEFAULT_ARTIFACTS_DIR", "artifacts")
    max_artifact_mb: int = _int("MAX_ARTIFACT_MB", 20)
    e2b_template: str | None = os.getenv("E2B_TEMPLATE") or None
    e2b_sandbox_timeout_seconds: int = _int("E2B_SANDBOX_TIMEOUT_SECONDS", 300)
    e2b_code_timeout_seconds: int = _int("E2B_CODE_TIMEOUT_SECONDS", 60)
    e2b_allow_internet: bool = _bool("E2B_ALLOW_INTERNET", False)


settings = Settings()
