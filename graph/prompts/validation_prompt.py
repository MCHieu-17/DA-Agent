from langchain_core.prompts import ChatPromptTemplate

validation_prompt = ChatPromptTemplate.from_messages([
    ("system", """Act as a data-answer QA reviewer. Mark valid only when the answer addresses the request, numerical claims are supported by evidence, assumptions are disclosed, and requested charts are present. Give concise actionable feedback when invalid."""),
    ("human", "Question: {user_question}\n\nEvidence: {evidence}\n\nAnswer: {final_answer}"),
])
