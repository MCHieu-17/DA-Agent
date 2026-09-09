import json
from graph.llms import get_node_llm
from graph.prompts import coder_prompt
from graph.state import CodeOutput
from graph.recovery import model_failure
from graph.utils import analysis_context, current_step

def coder_node(state):
    try:
        result = (coder_prompt | get_node_llm("coder").with_structured_output(CodeOutput)).invoke({
            **analysis_context(state, "coder"), "current_step": json.dumps(current_step(state), ensure_ascii=False),
        })
        return {"code": result.code, "execution_status": None, "execution_error": None,
                "execution_output": None, "traceback": None}
    except Exception as exc:
        return model_failure("Coder", exc)
