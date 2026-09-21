"""Configuration for the local-only LangGraph data agent."""

import os

from dotenv import load_dotenv


load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _env_nonnegative_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 0:
        raise ValueError(f"{name} must be zero or a positive integer.")
    return value


LLM_PROVIDER = os.getenv("DA_LLM_PROVIDER", "gemini").strip().lower()
LLM_MODELS = {
    "gemini": "gemini-3.5-flash-lite",
    "deepseek": "deepseek-v4-flash",
}
LLM_MODEL = os.getenv("DA_LLM_MODEL", LLM_MODELS.get(LLM_PROVIDER, ""))
LLM_REQUEST_TIMEOUT_SECONDS = _env_int("DA_LLM_REQUEST_TIMEOUT_SECONDS", 30)
LLM_MAX_RETRIES = _env_nonnegative_int("DA_LLM_MAX_RETRIES", 2)
LLM_NODE_MAX_OUTPUT_TOKENS = {
    "router": 1024,
    "clarify": 256,
    "planner": 4096,
    "coder": 2048,
    "debugger": 2048,
    "synthetic": 2048,
    "verification": 2048,
    "chat": 1024,
}

# Retry budgets exclude the first attempt.
MAX_DEBUG_RETRIES_PER_STEP = 2
MAX_REPLANS = 1
MAX_ANSWER_REVISIONS = 1
PLAN_MAX_STEPS = 6
GRAPH_RECURSION_LIMIT = 8 + (MAX_REPLANS + 1) * (
    1 + PLAN_MAX_STEPS * (2 + 2 * MAX_DEBUG_RETRIES_PER_STEP)
    + 2 * (MAX_ANSWER_REVISIONS + 1)
)

HISTORY_MAX_MESSAGES = 6
HISTORY_MAX_CHARS = 12_000
USER_INPUT_MAX_CHARS = _env_int("DA_MAX_MESSAGE_CHARS", 8_000)
PROMPT_EVIDENCE_MAX_CHARS = 24_000
VERIFICATION_EVIDENCE_MAX_CHARS = 128_000

CSV_ALLOWED_EXTENSIONS = frozenset({".csv"})
CSV_READ_OPTIONS = {
    "encoding": "utf-8-sig",
    "sep": ",",
    "keep_default_na": True,
}
PROFILE_VERSION = 3
PROFILE_CHUNK_SIZE = 10_000
PROFILE_SAMPLE_ROWS = 5_000
PROFILE_SAMPLE_SEED = 42
PROFILE_EXAMPLE_ROWS = 3
PROFILE_TOP_K = 5
PROFILE_MAX_CHARS = 20_000
PROFILE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%d/%m/%Y",
)

ARTIFACTS_DIR = "./artifacts"
ARTIFACT_ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".html", ".csv"})
RESULT_PREVIEW_ROWS = 20
EXECUTION_TIMEOUT_SECONDS = _env_int("DA_EXECUTION_TIMEOUT_SECONDS", 60)
EXECUTION_ERROR_MAX_CHARS = 12_000
EXECUTION_MATPLOTLIB_BACKEND = "Agg"


def validate_configuration() -> None:
    if LLM_PROVIDER not in LLM_MODELS:
        raise ValueError(
            f"Unsupported provider {LLM_PROVIDER!r}; choose 'gemini' or 'deepseek'."
        )
    required = {
        "router", "clarify", "planner", "coder", "debugger",
        "synthetic", "verification", "chat",
    }
    if required - LLM_NODE_MAX_OUTPUT_TOKENS.keys():
        raise ValueError("Missing node output-token limit.")


validate_configuration()
