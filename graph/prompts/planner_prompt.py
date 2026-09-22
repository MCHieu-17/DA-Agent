from langchain_core.prompts import ChatPromptTemplate

INITIAL_PLANNER_SYSTEM_PROMPT = """You plan data analysis. Return a small ordered plan, never code.
Use only four kinds: explore, query, visualize, custom_compute. Prefer the first three.
For vague requests, make the smallest reasonable assumptions from the catalog and record them.
Each step needs an observable success criterion."""

REPLAN_SYSTEM_PROMPT = """You revise a data-analysis plan after evidence or validation feedback. Return only remaining useful steps, never code. Prefer tools over custom_compute and do not repeat completed work."""

initial_planner_prompt = ChatPromptTemplate.from_messages([
    ("system", INITIAL_PLANNER_SYSTEM_PROMPT),
    ("human", "History:\n{history}\n\nRequest: {current_question}\n\nCatalog:\n{schema_str}"),
])

replan_prompt = ChatPromptTemplate.from_messages([
    ("system", REPLAN_SYSTEM_PROMPT),
    ("human", "History:\n{history}\n\nRequest: {current_question}\n\nCatalog:\n{schema_str}\n\nCompleted evidence:\n{past_steps}\n\nValidation/error feedback:\n{feedback}"),
])
