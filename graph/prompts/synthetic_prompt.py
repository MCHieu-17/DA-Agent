from langchain_core.prompts import ChatPromptTemplate

synthetic_prompt = ChatPromptTemplate.from_messages([
    ("system", """Answer in the user's language using only the supplied evidence. State material assumptions and limitations. Do not invent figures. Embed PNG/JPG artifacts with Markdown when relevant."""),
    ("human", "Question: {user_question}\n\nAssumptions: {assumptions}\n\nEvidence:\n{past_steps}\n\nArtifacts: {artifacts}"),
])
