from graph.state import ValidatorOutput
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_validator_llm = llm.with_structured_output(ValidatorOutput)

system_prompt = "Bạn là chuyên gia kiểm duyệt. Hãy đánh giá xem 'Kết quả cuối cùng' đã giải quyết trọn vẹn 'Câu hỏi' của người dùng chưa."

prompt = ChatPromptTemplate.from_messages([
        ("system", ""),
        ("human", "Câu hỏi: {question}\n\nKết quả cuối cùng:\n{output}")
    ])

validator_chain = prompt | structured_validator_llm