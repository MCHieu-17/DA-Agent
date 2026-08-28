from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import CoderOutput

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_coder_llm = llm.with_structured_output(CoderOutput)


prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_question}")
    ])

coder_chain = prompt | structured_coder_llm