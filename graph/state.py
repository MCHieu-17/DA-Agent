from typing import Annotated, List, Optional, Literal, TypedDict, Dict, Required
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ========================= #
#       SCHEMA FOR LLM      #
# ========================= #
# 1. Schema for Router
class RouteDecision(BaseModel):
    intent: Literal["chat", "analysis", "clarify_needed"] = Field(
        description="Nhãn phân loại của câu hỏi"
    )
# 2. Schema for clarify question
class ClarifyDecision(BaseModel):
    clarifying_question: str = Field(
        description="Câu hỏi ngắn gọn để hỏi lại user, làm rõ ý định phân tích dữ liệu."
    )
    reason: str = Field(
        description="Lý do ngắn gọn vì sao câu hỏi gốc chưa đủ rõ để phân tích."
    )
# 3. Schema for planner
class AnalysisPlan(BaseModel):
    steps: list[str] = Field(description="Danh sách các bước logic ngắn gọn để phân tích dữ liệu")

# 4. Schema for coder 
class CoderOutput(BaseModel):
    code: str = Field(description="Mã Python được tạo ra để thực thi. Không bao gồm markdown formatting (như ```python).")

# 5. Schema for validator
class ValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True nếu kết quả đã trả lời đủ và đúng trọng tâm câu hỏi gốc. False nếu chưa.")
    feedback: str = Field(description="Lý do chưa đạt và gợi ý hướng xử lý tiếp (chỉ ghi khi False).")

# 6. Schema for synthetic
class SyntheticOutput(BaseModel):
    final_answer: str = Field(
        description="Câu trả lời cuối cùng, toàn diện, dùng Markdown. Nếu có ảnh/biểu đồ trong artifacts, HÃY NHÚNG vào bằng cú pháp ![Mô tả](đường_dẫn_file)."
    )
# ========================= #
#       SCHEMA FOR GRAPH    #
# ========================= #
class DataAgentState(TypedDict):
    # --- Lịch sử chat ---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- Dataset & schema ---
    file_paths: List[str] # Đường dẫn các file csv
    schema_str: Optional[str] # Schema của các file csv
    schema_file_paths: Optional[List[str]]  # bộ file đã dùng để tạo schema_str

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
    artifacts_dir: Required[str] # Chỗ lưu ảnh các biểu đồ

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

    # --- Validation & output ---
    is_sufficient: Optional[bool]
    artifacts: List[str]
    final_answer: Optional[str]
    validation_feedback: Optional[str]
