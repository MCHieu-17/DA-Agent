import json
from graph.llms import get_node_llm
from graph.prompts import debugger_prompt
from graph.state import CodeOutput
from graph.recovery import model_failure
from graph.utils import analysis_context, current_step, truncate_text

def debug_node(state):
    count = state["debug_count"] + 1
    try:
        result = (debugger_prompt | get_node_llm("debugger").with_structured_output(CodeOutput)).invoke({
            **analysis_context(state, "debugger"), "current_step": json.dumps(current_step(state), ensure_ascii=False),
            "code": state.get("code", ""), "error": state.get("traceback", ""),
            "stdout": truncate_text(state.get("execution_output"), 4000),
        })
        return {"code": result.code, "debug_count": count}
    except Exception as exc:
        return {"debug_count": count, **model_failure("Debug", exc)}
