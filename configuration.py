"""Application-level configuration."""

import os


# Provider hỗ trợ: "gemini", "deepseek", "self_host".
# Ví dụ DeepSeek: LLM_PROVIDER = "deepseek", LLM_MODEL = "deepseek-v4-flash".
# Với self-host, LLM_MODEL phải là tên model đã pull trong Ollama.
LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini-3.5-flash-lite"

# LLM_PROVIDER = "self_host"
# LLM_MODEL = "gemma4:12b"