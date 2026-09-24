from graph.llms import llm
from graph.prompts import chat_prompt
from graph.state import DataAgentState
from graph.utils import format_answer_history, latest_user_question


chat_chain = chat_prompt | llm


def chat_node(state: DataAgentState):
    response = chat_chain.invoke({
        "conversation_history": format_answer_history(state.get("answer_history")),
        "user_question": latest_user_question(state["messages"]),
    })
    return {"final_answer": response.content}
