from langchain_core.prompts import ChatPromptTemplate

action_prompt = ChatPromptTemplate.from_messages([
    ("system", """Choose one action for the supplied step. Prefer a listed tool.
You may select code only for custom_compute when no listed tool can do the work. Never choose code for explore, query, or visualize.
When selecting a tool, provide only valid JSON-like arguments. For code, provide a concise capability gap as fallback_reason."""),
    ("human", "Tool catalog:\n{tool_catalog}\n\nData catalog:\n{profile_summary}\n\nCurrent step:\n{step}\n\nPrior evidence:\n{past_steps}"),
])
