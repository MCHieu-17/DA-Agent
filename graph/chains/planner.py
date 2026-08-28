from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from graph.state import AnalysisPlan

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_planner_llm = llm.with_structured_output(AnalysisPlan)

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    ("human", "{human_prompt}")
])

planner_chain = prompt | structured_planner_llm