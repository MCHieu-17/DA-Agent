from langchain_core.messages import AIMessage

from graph.llms import llm
from graph.prompts import chat_prompt
from graph.state import DataAgentState


chat_chain = chat_prompt | llm


def chat_node(state: DataAgentState):
    response = chat_chain.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response.content)]}
