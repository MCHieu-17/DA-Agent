from langchain_core.prompts import ChatPromptTemplate

SYSTEM_NORMAL = """Write one Python cell for a sandboxed, headless environment. Use only the supplied sandbox paths and installed common data libraries. Do not install packages, access the network, or read paths outside /home/user/data. Save requested charts/files under /home/user/artifacts. Print concise factual results. Return code only."""
SYSTEM_ERROR = """Repair the Python cell using the sandbox error. Keep the same safety rules: no network, no package installs, input only under /home/user/data, output only under /home/user/artifacts. Return code only."""

normal_prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_NORMAL), ("human", "Objective: {current_step}\nAssumptions: {assumptions}\nFiles: {sandbox_file_map}\nRelevant evidence: {past_steps}")])
error_prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_ERROR), ("human", "Objective: {current_step}\nFiles: {sandbox_file_map}\nPrevious code:\n{code}\n\nError:\n{traceback}")])
