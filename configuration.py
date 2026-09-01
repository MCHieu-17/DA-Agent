"""Cấu hình tập trung cho toàn bộ Data Analysis Agent.

Chỉ chỉnh các giá trị trong file này để thay đổi model, retry/replan,
schema extraction, artifacts và giới hạn của code executor.
Không lưu API key tại đây; API key vẫn được đọc từ file ``.env``.
"""

import hashlib
import os


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


# ========================= #
#          LLM              #
# ========================= #

# Chỉ cần đổi provider tại đây: "gemini", "deepseek" hoặc "self_host".
LLM_PROVIDER = os.getenv("DA_LLM_PROVIDER", "gemini").strip().lower()

# Model mặc định tương ứng với từng provider.
LLM_MODELS = {
    "gemini": "gemini-3.5-flash-lite",
    "deepseek": "deepseek-v4-flash",
    "self_host": "gemma4:12b",
}
LLM_MODEL = os.getenv("DA_LLM_MODEL", LLM_MODELS.get(LLM_PROVIDER, ""))

# Tham số chung được truyền cho mọi provider. Chỉ thêm option thực sự được tất
# cả provider hỗ trợ. Gemini hiện tại dùng sampling mặc định cố định nên không
# đặt ``temperature`` ở đây.
LLM_COMMON_OPTIONS = {}

# Tham số riêng cho từng provider; ghi đè LLM_COMMON_OPTIONS nếu trùng key.
LLM_PROVIDER_OPTIONS = {
    "gemini": {},
    "deepseek": {"temperature": 0.0},
    "self_host": {"temperature": 0.0},
}

# Guard cho mỗi request model. ``max_retries`` là retry ở transport/provider,
# độc lập với retry code execution của graph.
LLM_REQUEST_TIMEOUT_SECONDS = _env_int("DA_LLM_REQUEST_TIMEOUT_SECONDS", 30)
LLM_MAX_RETRIES = _env_int("DA_LLM_MAX_RETRIES", 2)
LLM_NODE_MAX_OUTPUT_TOKENS = {
    "router": 64,
    "clarify": 256,
    "planner": 384,
    "coder": 2048,
    "debugger": 512,
    "synthetic": 1024,
    "validator": 256,
    "chat": 1024,
}


# ========================= #
#       GRAPH CONTROL       #
# ========================= #

MAX_RETRIES = 3
MAX_REPLANS = 3
HISTORY_MAX_MESSAGES = 6
HISTORY_MAX_CHARS = 12_000
USER_INPUT_MAX_CHARS = _env_int("DA_MAX_MESSAGE_CHARS", 8_000)
PLAN_MAX_STEPS = 3
GRAPH_RECURSION_LIMIT = 128
PROMPT_EVIDENCE_MAX_CHARS = 24_000

# False: debug node phân loại lỗi deterministic rồi chuyển thẳng cho error-coder.
# True: gọi thêm một lượt LLM debugger cho mỗi retry.
DEBUGGER_LLM_ENABLED = False

# False: configuration.py luôn là nguồn cấu hình duy nhất.
# True: request/state có thể ghi đè max_retries, max_replans,
# execution_timeout_seconds và artifacts_dir.
ALLOW_STATE_CONFIG_OVERRIDES = False


# ========================= #
#       CSV / SCHEMA        #
# ========================= #

CSV_ALLOWED_EXTENSIONS = frozenset({".csv"})
CSV_HEADER_ENCODING = "utf-8-sig"
SCHEMA_CHUNK_SIZE = 10_000
SCHEMA_SAMPLE_ROWS = 3
SCHEMA_HASH_ALGORITHM = "sha256"
SCHEMA_HASH_BLOCK_BYTES = 1024 * 1024
SCHEMA_MAX_CHARS = 20_000
# Metadata path/size/mtime_ns đủ nhanh cho local workflow. Bật True nếu cần
# phát hiện trường hợp hiếm file đổi nội dung nhưng giữ nguyên size và mtime.
SCHEMA_CACHE_STRICT_HASH = False


# ========================= #
#        ARTIFACTS          #
# ========================= #

ARTIFACTS_DIR = "./artifacts"
ARTIFACT_ALLOWED_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".html", ".csv"}
)
ARTIFACT_MAX_FILES = _env_int("DA_MAX_ARTIFACTS_PER_RUN", 20)
ARTIFACT_TOTAL_LIMIT_MB = _env_int("DA_ARTIFACT_TOTAL_LIMIT_MB", 250)


# ========================= #
#      CODE EXECUTOR        #
# ========================= #

EXECUTION_TIMEOUT_SECONDS = _env_int("DA_EXECUTOR_TIMEOUT_SECONDS", 60)
EXECUTION_MIN_TIMEOUT_SECONDS = 1
EXECUTION_MAX_TIMEOUT_SECONDS = 300
EXECUTION_MEMORY_LIMIT_MB = _env_int("DA_EXECUTION_MEMORY_LIMIT_MB", 2048)
EXECUTION_FILE_SIZE_LIMIT_MB = 100
EXECUTION_MAX_OPEN_FILES = _env_int("DA_EXECUTION_MAX_OPEN_FILES", 128)
# RLIMIT_NPROC is scoped to the Linux user, not just the executor subprocess.
# Keep it disabled while LangGraph and the executor share a desktop user.
EXECUTION_MAX_PROCESSES: int | None = None
EXECUTION_THREAD_LIMIT = 1
EXECUTION_CPU_GRACE_SECONDS = 2
EXECUTION_ERROR_MAX_CHARS = 12_000
EXECUTION_STDOUT_MAX_BYTES = _env_int("DA_EXECUTOR_MAX_STDOUT_BYTES", 256_000)
EXECUTION_STDERR_MAX_BYTES = _env_int("DA_EXECUTOR_MAX_STDERR_BYTES", 64_000)
EXECUTION_TEMP_DIR = "/tmp"
EXECUTION_MATPLOTLIB_BACKEND = "Agg"
EXECUTION_ISOLATED_PYTHON = True
EXECUTION_LOCALE = "C.UTF-8"

# Các module code do LLM sinh ra được phép import.
EXECUTION_ALLOWED_IMPORTS = frozenset(
    {
        "collections",
        "datetime",
        "duckdb",
        "json",
        "math",
        "matplotlib",
        "numpy",
        "pandas",
        "plotly",
        "re",
        "seaborn",
        "statistics",
    }
)

EXECUTION_BLOCKED_CALLS = frozenset(
    {"__import__", "breakpoint", "compile", "eval", "exec", "input", "open"}
)
EXECUTION_WRITE_METHODS = frozenset(
    {"savefig", "to_csv", "write_html", "write_image"}
)


def state_override(state: dict, key: str, configured_value):
    """Return a request override only when explicitly enabled above."""
    if ALLOW_STATE_CONFIG_OVERRIDES and key in state:
        return state[key]
    return configured_value


def validate_configuration() -> None:
    """Fail fast with a clear message when a configured value is invalid."""
    if LLM_PROVIDER not in LLM_MODELS:
        raise ValueError(
            f"LLM_PROVIDER={LLM_PROVIDER!r} không hợp lệ; chọn một trong {sorted(LLM_MODELS)}."
        )
    if LLM_PROVIDER not in LLM_PROVIDER_OPTIONS:
        raise ValueError(f"Thiếu LLM_PROVIDER_OPTIONS cho {LLM_PROVIDER!r}.")
    if LLM_REQUEST_TIMEOUT_SECONDS < 1 or LLM_MAX_RETRIES < 0:
        raise ValueError(
            "LLM_REQUEST_TIMEOUT_SECONDS phải >= 1 và LLM_MAX_RETRIES phải >= 0."
        )
    if not LLM_NODE_MAX_OUTPUT_TOKENS or any(
        value < 1 for value in LLM_NODE_MAX_OUTPUT_TOKENS.values()
    ):
        raise ValueError("Mọi LLM_NODE_MAX_OUTPUT_TOKENS phải >= 1.")
    required_llm_nodes = {
        "router",
        "clarify",
        "planner",
        "coder",
        "debugger",
        "synthetic",
        "validator",
        "chat",
    }
    missing_llm_nodes = required_llm_nodes - LLM_NODE_MAX_OUTPUT_TOKENS.keys()
    if missing_llm_nodes:
        raise ValueError(
            f"Thiếu LLM_NODE_MAX_OUTPUT_TOKENS cho {sorted(missing_llm_nodes)}."
        )
    if MAX_RETRIES < 0 or MAX_REPLANS < 0:
        raise ValueError("MAX_RETRIES và MAX_REPLANS phải >= 0.")
    if (
        HISTORY_MAX_MESSAGES < 1
        or HISTORY_MAX_CHARS < 1
        or USER_INPUT_MAX_CHARS < 1
    ):
        raise ValueError(
            "HISTORY_MAX_MESSAGES, HISTORY_MAX_CHARS và "
            "USER_INPUT_MAX_CHARS phải >= 1."
        )
    if PLAN_MAX_STEPS < 1 or GRAPH_RECURSION_LIMIT < 1:
        raise ValueError("PLAN_MAX_STEPS và GRAPH_RECURSION_LIMIT phải >= 1.")
    if PROMPT_EVIDENCE_MAX_CHARS < 1:
        raise ValueError("PROMPT_EVIDENCE_MAX_CHARS phải >= 1.")
    if SCHEMA_CHUNK_SIZE < 1 or SCHEMA_SAMPLE_ROWS < 0:
        raise ValueError("SCHEMA_CHUNK_SIZE phải >= 1 và SCHEMA_SAMPLE_ROWS phải >= 0.")
    if SCHEMA_HASH_BLOCK_BYTES < 1:
        raise ValueError("SCHEMA_HASH_BLOCK_BYTES phải >= 1.")
    if SCHEMA_MAX_CHARS < 1:
        raise ValueError("SCHEMA_MAX_CHARS phải >= 1.")
    if SCHEMA_HASH_ALGORITHM not in hashlib.algorithms_available:
        raise ValueError(f"Hash algorithm không được hỗ trợ: {SCHEMA_HASH_ALGORITHM!r}.")
    if not CSV_ALLOWED_EXTENSIONS or any(
        not extension.startswith(".") for extension in CSV_ALLOWED_EXTENSIONS
    ):
        raise ValueError("CSV_ALLOWED_EXTENSIONS phải chứa extension bắt đầu bằng dấu chấm.")
    if not ARTIFACTS_DIR:
        raise ValueError("ARTIFACTS_DIR không được để trống.")
    if ARTIFACT_MAX_FILES < 1 or ARTIFACT_TOTAL_LIMIT_MB < 1:
        raise ValueError("ARTIFACT_MAX_FILES và ARTIFACT_TOTAL_LIMIT_MB phải >= 1.")
    if not (
        1
        <= EXECUTION_MIN_TIMEOUT_SECONDS
        <= EXECUTION_TIMEOUT_SECONDS
        <= EXECUTION_MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(
            "Timeout phải thỏa 1 <= MIN_TIMEOUT <= TIMEOUT <= MAX_TIMEOUT."
        )
    positive_limits = {
        "EXECUTION_MEMORY_LIMIT_MB": EXECUTION_MEMORY_LIMIT_MB,
        "EXECUTION_FILE_SIZE_LIMIT_MB": EXECUTION_FILE_SIZE_LIMIT_MB,
        "EXECUTION_MAX_OPEN_FILES": EXECUTION_MAX_OPEN_FILES,
        "EXECUTION_THREAD_LIMIT": EXECUTION_THREAD_LIMIT,
        "EXECUTION_ERROR_MAX_CHARS": EXECUTION_ERROR_MAX_CHARS,
        "EXECUTION_STDOUT_MAX_BYTES": EXECUTION_STDOUT_MAX_BYTES,
        "EXECUTION_STDERR_MAX_BYTES": EXECUTION_STDERR_MAX_BYTES,
    }
    if EXECUTION_MAX_PROCESSES is not None:
        positive_limits["EXECUTION_MAX_PROCESSES"] = EXECUTION_MAX_PROCESSES
    invalid_limits = [name for name, value in positive_limits.items() if value < 1]
    if invalid_limits:
        raise ValueError(f"Các giới hạn sau phải >= 1: {invalid_limits}.")
    if EXECUTION_CPU_GRACE_SECONDS < 0:
        raise ValueError("EXECUTION_CPU_GRACE_SECONDS phải >= 0.")


validate_configuration()
