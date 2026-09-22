from langchain_core.prompts import ChatPromptTemplate

from graph.llms import llm
from graph.state import DataAgentState, RouteDecision
from graph.utils import format_history, latest_user_question

router_chain = ChatPromptTemplate.from_messages([
    ("system", """Classify the latest user request as exactly one label.
chat: general conversation or general knowledge that does not require computing on uploaded files.
analysis: any request that needs uploaded data, including vague requests, follow-ups, table/schema questions, calculations, exports, or charts.
Use conversation history for follow-ups. Never return clarify_needed."""),
    ("human", "History:\n{history}\n\nData catalog:\n{profile_summary}\n\nLatest request:\n{question}"),
]) | llm.with_structured_output(RouteDecision)


def question_router(state: DataAgentState) -> str:
    decision = router_chain.invoke({"history": format_history(state["messages"], exclude_last=True), "question": latest_user_question(state["messages"]), "profile_summary": state.get("profile_summary", "No readable data.")})
    return decision.intent
