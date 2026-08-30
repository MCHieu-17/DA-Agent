from graph.llms import llm
from graph.prompts import debugger_prompt
from graph.state import DataAgentState


debug_chain = debugger_prompt | llm


def debug_node(state: DataAgentState):
    response = debug_chain.invoke({
        "code": state.get("code"),
        "execution_error": state.get("execution_error"),
        "traceback": state.get("traceback"),
    })

    return {
        "debug_feedback": response.content,
    }
