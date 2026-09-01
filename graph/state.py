from typing import Annotated, List, Optional, Literal, TypedDict, Required
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from configuration import PLAN_MAX_STEPS


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
    steps: list[str] = Field(
        min_length=1,
        max_length=PLAN_MAX_STEPS,
        description=(
            "Danh sách bước phân tích. Mặc định dùng đúng 1 bước thực thi hoàn chỉnh; "
            f"không bao giờ vượt quá {PLAN_MAX_STEPS} bước."
        ),
    )

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
# ========================== #
#       SCHEMA FOR GRAPH     #
# ========================== #
class DataAgentState(TypedDict, total=False):
    # --- Lịch sử chat ---
    messages: Required[Annotated[List[BaseMessage], add_messages]]

    # --- Dataset & schema ---
    file_paths: List[str] # Đường dẫn các file csv
    # Production worker keeps schema paths private and exposes only these
    # fixed container paths to generated code.
    execution_file_paths: List[str]
    schema_str: Optional[str] # Schema của các file csv
    schema_file_paths: Optional[List[str]]  # bộ file đã dùng để tạo schema_str
    schema_file_fingerprints: List[str]
    schema_valid: bool
    schema_errors: List[str]

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
    artifacts_dir: str # Thư mục gốc lưu artifacts
    execution_artifacts_dir: str
    artifact_run_id: str
    service_run_id: str
    execution_timeout_seconds: int

    # --- Debug ---
    debug_feedback: Optional[str]


    # --- Retry / Replan control ---
    retry_count: int
    max_retries: int
    replan_count: int
    max_replans: int
    replan_reason: Optional[Literal["execution", "validation"]]


    # --- Validation & output ---
    is_sufficient: Optional[bool]
    artifacts: List[str]
    final_answer: Optional[str]
    validation_feedback: Optional[str]
    workflow_status: Literal["running", "success", "needs_input", "failed"]
    failure_reason: Optional[str]
    node_error: Optional[str]
