"""Cấu hình model, schema CSV và thực thi Python local.

Chỉnh tại đây hoặc dùng các biến môi trường được chỉ rõ bên dưới.
API key được đọc từ .env; retry LLM độc lập với số lần debug code.
"""

import os


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# Model: giữ ba provider hiện có.
LLM_PROVIDER = os.getenv("DA_LLM_PROVIDER", "gemini").strip().lower()
LLM_MODELS = {
    "gemini": "gemini-3.5-flash-lite",
    "deepseek": "deepseek-v4-flash",
    "self_host": "gemma4:12b",
}
LLM_MODEL = os.getenv("DA_LLM_MODEL", LLM_MODELS.get(LLM_PROVIDER, ""))
LLM_COMMON_OPTIONS = {}
LLM_PROVIDER_OPTIONS = {
    "gemini": {},
    "deepseek": {"temperature": 0.0},
    "self_host": {"temperature": 0.0},
}
LLM_REQUEST_TIMEOUT_SECONDS = _env_int("DA_LLM_REQUEST_TIMEOUT_SECONDS", 30)
LLM_MAX_RETRIES = _env_int("DA_LLM_MAX_RETRIES", 2)
LLM_NODE_MAX_OUTPUT_TOKENS = {
    "router": 1024,
    "clarify": 256,
    "planner": 4096,
    "coder": 2048,
    "debugger": 2048,  # Debug trả về toàn bộ code đã sửa.
    "synthetic": 2048,
    "verification": 2048,
    "chat": 1024,
}

# Retry budgets exclude the initial attempt.
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

# Mặc định cấu hình chỉ lấy từ file này. Khi bật, state có thể ghi đè
# execution_timeout_seconds và artifacts_dir.
ALLOW_STATE_CONFIG_OVERRIDES = False

# Full-file basic statistics, bounded sample for distribution statistics.
CSV_ALLOWED_EXTENSIONS = frozenset({".csv"})
CSV_READ_OPTIONS = {"encoding": "utf-8-sig", "sep": ",", "keep_default_na": True}
PROFILE_VERSION = 2
PROFILE_CHUNK_SIZE = 10_000
PROFILE_SAMPLE_ROWS = 5_000
PROFILE_SAMPLE_SEED = 42
PROFILE_EXAMPLE_ROWS = 3
PROFILE_TOP_K = 5
PROFILE_MAX_CHARS = 20_000
PROFILE_CACHE_STRICT_HASH = False
PROFILE_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y")
RESULT_PREVIEW_ROWS = 20

# Python local dùng cùng interpreter và môi trường với agent.
ARTIFACTS_DIR = "./artifacts"
ARTIFACT_ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".html", ".csv"})
EXECUTION_TIMEOUT_SECONDS = _env_int("DA_EXECUTOR_TIMEOUT_SECONDS", 300 if os.getenv("DA_ENVIRONMENT") == "production" else 60)
EXECUTION_MIN_TIMEOUT_SECONDS = 1
EXECUTION_MAX_TIMEOUT_SECONDS = 300
EXECUTION_ERROR_MAX_CHARS = 12_000
EXECUTION_MATPLOTLIB_BACKEND = "Agg"
EXECUTION_TRANSIENT_RETRIES = _env_int("DA_EXECUTOR_TRANSIENT_RETRIES", 1)

# Fail closed unless local development is explicitly requested.
ENVIRONMENT = os.getenv("DA_ENVIRONMENT", "development")
EXECUTOR_BACKEND = os.getenv("DA_EXECUTOR_BACKEND", "gvisor")
SANDBOX_IMAGE = os.getenv("DA_SANDBOX_IMAGE", "")
SANDBOX_CPUS = 2
SANDBOX_MEMORY_MB = 4096
SANDBOX_PIDS = 128
SANDBOX_DISK_MB = 20 * 1024
EXECUTION_LOG_MAX_BYTES = 1024 * 1024
EXECUTION_MANIFEST_MAX_BYTES = 1024 * 1024
EXECUTION_MAX_FILES = 1000
PANDAS_MAX_INPUT_BYTES = 100 * 1024 * 1024
RUN_TIMEOUT_SECONDS = _env_int("DA_RUN_TIMEOUT_SECONDS", 900)
RUN_TOKEN_BUDGET = _env_int("DA_RUN_TOKEN_BUDGET", 120_000)
VERIFICATION_TOKEN_RESERVE = 8000
LLM_MAX_CONCURRENCY = _env_int("DA_LLM_MAX_CONCURRENCY", 5)
SNAPSHOT_DIR = os.getenv("DA_SNAPSHOT_DIR", "./artifacts/snapshots")
SOURCE_REGISTRY_PATH = os.getenv("DA_SOURCE_REGISTRY", "./deploy/sources.json")
AUTH_REGISTRY_PATH = os.getenv("DA_AUTH_REGISTRY", "./deploy/users.json")
QUEUE_DSN_ENV = "DA_QUEUE_DSN"


def state_override(state: dict, key: str, configured_value):
    """Chỉ nhận cấu hình từ state khi chủ động bật ở trên."""
    if ALLOW_STATE_CONFIG_OVERRIDES and key in state:
        return state[key]
    return configured_value


def validate_configuration() -> None:
    if ENVIRONMENT not in {"development", "production"} or EXECUTOR_BACKEND not in {"local", "gvisor"}:
        raise ValueError("Invalid environment/executor backend.")
    if ENVIRONMENT == "production" and EXECUTOR_BACKEND != "gvisor":
        raise ValueError("Production requires gVisor; local execution is forbidden.")
    if LLM_PROVIDER not in LLM_MODELS or LLM_PROVIDER not in LLM_PROVIDER_OPTIONS:
        raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")
    required = {"router", "clarify", "planner", "coder", "debugger", "synthetic", "verification", "chat"}
    if required - LLM_NODE_MAX_OUTPUT_TOKENS.keys():
        raise ValueError("Missing node token budget.")
    if any(value < 0 for value in (
        MAX_DEBUG_RETRIES_PER_STEP, MAX_REPLANS, MAX_ANSWER_REVISIONS, LLM_MAX_RETRIES,
        EXECUTION_TRANSIENT_RETRIES,
    )):
        raise ValueError("Retry budgets must be >= 0.")
    if any(value < 1 for value in (
        PLAN_MAX_STEPS, PROFILE_CHUNK_SIZE, PROFILE_SAMPLE_ROWS, PROFILE_MAX_CHARS,
        PROFILE_TOP_K, RESULT_PREVIEW_ROWS, HISTORY_MAX_MESSAGES, HISTORY_MAX_CHARS,
        USER_INPUT_MAX_CHARS, PROMPT_EVIDENCE_MAX_CHARS, EXECUTION_ERROR_MAX_CHARS,
        LLM_REQUEST_TIMEOUT_SECONDS, *LLM_NODE_MAX_OUTPUT_TOKENS.values(),
    )):
        raise ValueError("Size and time budgets must be positive.")
    if not 1 <= EXECUTION_MIN_TIMEOUT_SECONDS <= EXECUTION_TIMEOUT_SECONDS <= EXECUTION_MAX_TIMEOUT_SECONDS:
        raise ValueError("Invalid execution timeout.")
    if not ARTIFACTS_DIR or not CSV_ALLOWED_EXTENSIONS:
        raise ValueError("Artifact directory and CSV extensions are required.")


validate_configuration()
