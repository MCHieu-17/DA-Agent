from typing import Annotated, List, Optional, Literal, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    intent: Literal["chat", "analysis", "clarify_needed"] = Field(
        description="Nhãn phân loại của câu hỏi"
    )
# class DataAgentState(TypedDict):
#     # --- Lịch sử chat ---
#     messages: Annotated[List[BaseMessage], add_messages]

#     # --- Router / intent ---
#     user_question: str
#     intent: Literal["chat", "analysis", "clarify_needed"]

#     # --- Dataset & schema ---
#     dataset_id: Optional[str]
#     data_schema: Optional[dict]

#     # --- Planning ---
#     plan: List[str]
#     current_step_idx: int
#     past_steps: List[dict]  # [{step, code, stdout, artifacts}]

#     # --- Coder / Executor ---
#     code: Optional[str]
#     execution_status: Optional[Literal["success", "error"]]
#     execution_output: Optional[str]
#     execution_error: Optional[str]
#     traceback: Optional[str]

#     # --- Retry / Replan control ---
#     retry_count: int
#     max_retries: int
#     replan_count: int
#     max_replans: int

#     # --- Human in the loop ---
#     needs_human_review: bool
#     human_approved: Optional[bool]

#     # --- Validation & output ---
#     is_sufficient: Optional[bool]
#     artifacts: List[str]
#     final_answer: Optional[str]


# def init_state(user_question: str, dataset_id: Optional[str] = None) -> DataAgentState:
#     """Helper khởi tạo state mặc định cho một lượt chạy mới."""
#     return DataAgentState(
#         messages=[],
#         user_question=user_question,
#         intent="analysis",
#         dataset_id=dataset_id,
#         data_schema=None,
#         plan=[],
#         current_step_idx=0,
#         past_steps=[],
#         code=None,
#         execution_status=None,
#         execution_output=None,
#         execution_error=None,
#         traceback=None,
#         retry_count=0,
#         max_retries=3,
#         replan_count=0,
#         max_replans=2,
#         needs_human_review=False,
#         human_approved=None,
#         is_sufficient=None,
#         artifacts=[],
#         final_answer=None,
#     )
