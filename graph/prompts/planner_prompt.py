from langchain_core.prompts import ChatPromptTemplate
from graph.tool_capabilities import CHART_TOOL_LIMIT

INITIAL_PLANNER_SYSTEM_PROMPT = """You plan data analysis. Return a small ordered plan, never code.
Use only four kinds: explore, query, visualize, custom_compute. Prefer a tool-compatible kind, but use custom_compute whenever the requested output exceeds the documented capability of one tool execution.
""" + CHART_TOOL_LIMIT + """
Requests exceeding that limit must use one custom_compute step.
For vague requests, make the smallest reasonable assumptions from the catalog and record them.
Each step needs an observable success criterion."""

REPLAN_SYSTEM_PROMPT = """You revise a data-analysis plan after evidence or validation feedback. Return only remaining useful steps, never code. Prefer tools only when they can fully meet the remaining success criteria. """ + CHART_TOOL_LIMIT + """ Use custom_compute when the tool interface cannot produce the requested output. Do not repeat completed work."""

initial_planner_prompt = ChatPromptTemplate.from_messages([
    ("system", INITIAL_PLANNER_SYSTEM_PROMPT),
    ("human", "History:\n{history}\n\nRequest: {current_question}\n\nCatalog:\n{schema_str}"),
])

replan_prompt = ChatPromptTemplate.from_messages([
    ("system", REPLAN_SYSTEM_PROMPT),
    ("human", "History:\n{history}\n\nRequest: {current_question}\n\nCatalog:\n{schema_str}\n\nCompleted evidence:\n{past_steps}\n\nValidation/error feedback:\n{feedback}"),
])
