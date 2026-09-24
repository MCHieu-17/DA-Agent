from langchain_core.prompts import ChatPromptTemplate
from graph.tool_capabilities import CHART_TOOL_LIMIT

action_prompt = ChatPromptTemplate.from_messages([
    ("system", """Choose one action that completely satisfies the supplied step and the user's request.
Prefer a listed tool only when its documented interface can meet every part of the success criteria in one execution. You may choose code for any step kind when no listed tool can do so, or when prior evidence shows that a tool failed or produced an incomplete result. Do not use code merely to replace a capable tool.
""" + CHART_TOOL_LIMIT + """ When selecting code, give the concrete missing capability in fallback_reason. When selecting a tool, provide only valid JSON-like arguments."""),
    ("human", "User request:\n{user_question}\n\nTool catalog:\n{tool_catalog}\n\nData catalog:\n{profile_summary}\n\nCurrent step:\n{step}\n\nPrior evidence:\n{past_steps}"),
])
