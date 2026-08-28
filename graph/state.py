from typing import Annotated, List, Optional, Literal, TypedDict, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ========================= #
#       SCHEMA FOR LLM      #
# ========================= #
# 1. Router
class RouteDecision(BaseModel):
    intent: Literal["chat", "analysis", "clarify_needed"] = Field(
        description="Nhãn phân loại của câu hỏi"
    )
# 2. For clarify question
class ClarifyDecision(BaseModel):
    clarifying_question: str = Field(
        description="Câu hỏi ngắn gọn để hỏi lại user, làm rõ ý định phân tích dữ liệu."
    )
    reason: str = Field(
        description="Lý do ngắn gọn vì sao câu hỏi gốc chưa đủ rõ để phân tích."
    )
# 3. For planner
class AnalysisPlan(BaseModel):
    steps: list[str] = Field(description="Danh sách các bước logic ngắn gọn để phân tích dữ liệu")

# 4. Schema for coder 
class CoderOutput(BaseModel):
    code: str = Field(description="Mã Python được tạo ra để thực thi. Không bao gồm markdown formatting (như ```python).")

# ========================= #
#       SCHEMA FOR GRAPH    #
# ========================= #
class DataAgentState(TypedDict):
    # --- Lịch sử chat ---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- Dataset & schema ---
    file_paths: List[str]
    schema_str: Optional[str]




    # --- Planning ---
    plan: List[str]
    current_step_idx: int
    past_steps: List[dict]  # [{step, code, stdout, artifacts}]

    # --- Coder / Executor ---
    code: Optional[str]
    execution_status: Optional[Literal["success", "error"]]
    execution_output: Optional[str]
    execution_error: Optional[str]
    traceback: Optional[str]

    # --- Debug ---
    debug_feedback: Optional[str]


    # --- Retry / Replan control ---
    retry_count: int
    max_retries: int
    replan_count: int
    max_replans: int

    # # --- Human in the loop ---
    # needs_human_review: bool
    # human_approved: Optional[bool]

    # # --- Validation & output ---
    # is_sufficient: Optional[bool]
    # artifacts: List[str]
    # final_answer: Optional[str]

