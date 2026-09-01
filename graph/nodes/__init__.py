"""Lazy public node exports.

Importing a utility node such as ``graph.nodes.execution`` must not initialize
every LLM provider or require an API key. Building the full graph still resolves
the same public node names as before.
"""

from importlib import import_module


_NODE_EXPORTS = {
    "clarify_node": ("graph.nodes.clarifier", "clarify_node"),
    "coder_node": ("graph.nodes.coder", "coder_node"),
    "debug_node": ("graph.nodes.debugger", "debug_node"),
    "execution_node": ("graph.nodes.execution", "execution_node"),
    "planner_node": ("graph.nodes.planner", "planner_node"),
    "extract_schema_node": ("graph.nodes.schema_extractor", "extract_schema_node"),
    "synthetic_node": ("graph.nodes.synthetic", "synthetic_node"),
    "validate_node": ("graph.nodes.validation", "validate_node"),
    "chat_node": ("graph.nodes.chat", "chat_node"),
    "failure_node": ("graph.nodes.failure", "failure_node"),
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
