<<<<<<< HEAD
"""Lazy public node exports.

Importing a utility node such as ``graph.nodes.execution`` must not initialize
every LLM provider or require an API key. Building the full graph still resolves
the same public node names as before.
"""

from importlib import import_module


_NODE_EXPORTS = {
    "clarify_node": ("graph.nodes.clarifier", "clarify_node"),
    "debug_node": ("graph.nodes.debugger", "debug_node"),
    "execution_node": ("graph.nodes.execution", "execution_node"),
    "planner_node": ("graph.nodes.planner", "planner_node"),
    "data_profiling_node": ("graph.nodes.data_profiling", "data_profiling_node"),
    "coder_node": ("graph.nodes.coder", "coder_node"),
    "verification_node": ("graph.nodes.verification", "verification_node"),
    "finalize_node": ("graph.nodes.finalize", "finalize_node"),
    "synthetic_node": ("graph.nodes.synthetic", "synthetic_node"),
    "chat_node": ("graph.nodes.chat", "chat_node"),
}

__all__ = list(_NODE_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute_name = _NODE_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
=======
from graph.nodes.action_selector import action_selector_node
from graph.nodes.coder import coder_node
from graph.nodes.debugger import debug_node
from graph.nodes.execution import execution_node
from graph.nodes.planner import planner_node
from graph.nodes.schema_extractor import extract_schema_node
from graph.nodes.synthetic import synthetic_node
from graph.nodes.validation import validate_node
from graph.nodes.chat import chat_node
from graph.nodes.cleanup import cleanup_node
from graph.nodes.tool_executor import tool_executor_node

__all__ = ["action_selector_node", "coder_node", "debug_node", "execution_node", "planner_node", "extract_schema_node", "synthetic_node", "validate_node", "chat_node", "cleanup_node", "tool_executor_node"]
>>>>>>> restore-work
