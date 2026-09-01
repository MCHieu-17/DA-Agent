from langchain_core.messages import AIMessage

from graph.llms import get_node_llm
from graph.prompts import chat_prompt
from graph.state import DataAgentState
from graph.utils import bounded_messages


chat_chain = chat_prompt | get_node_llm("chat")


def chat_node(state: DataAgentState):
    try:
        response = chat_chain.invoke(
            {"messages": bounded_messages(state["messages"])}
        )
        content = response.content
        status = "success"
    except Exception:
        content = "Mình chưa thể trả lời lúc này. Bạn vui lòng thử lại sau."
        status = "failed"
    return {
        "messages": [AIMessage(content=content)],
        "workflow_status": status,
    }
