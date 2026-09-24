from langchain_core.prompts import ChatPromptTemplate

SYSTEM_NORMAL = """Write one Python cell for a sandboxed, headless environment. Use only the supplied sandbox paths and installed common data libraries. Do not install packages, access the network, or read paths outside /home/user/data. Save requested charts/files under /home/user/artifacts. Print concise factual results needed for the final answer. Return the structured CoderOutput object with its code field.
Meet every stated success criterion. If the request requires several charts in one image, create one matplotlib figure with the required subplots and save one PNG containing all of them."""
SYSTEM_ERROR = """Repair the Python cell using the sandbox error while meeting the original objective and success criteria. Keep the same safety rules: no network, no package installs, input only under /home/user/data, output only under /home/user/artifacts. Return the structured CoderOutput object with its code field."""

normal_prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_NORMAL), ("human", "User request: {user_question}\nObjective: {current_step}\nSuccess criteria: {success_criteria}\nWhy code was selected: {fallback_reason}\nAssumptions: {assumptions}\nFiles: {sandbox_file_map}\nRelevant evidence: {past_steps}")])
error_prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_ERROR), ("human", "User request: {user_question}\nObjective: {current_step}\nSuccess criteria: {success_criteria}\nAssumptions: {assumptions}\nFiles: {sandbox_file_map}\nPrevious code:\n{code}\n\nError:\n{traceback}")])
