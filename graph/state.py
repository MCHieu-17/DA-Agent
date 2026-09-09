"""Structured plans, execution evidence, and graph state."""
from typing import Annotated, Literal, Required, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, model_validator
from configuration import PLAN_MAX_STEPS

class RouteDecision(BaseModel):
    intent: Literal["chat", "analysis", "clarify_needed"]
    response: str | None = None
    analysis_request: str | None = None
    columns: dict[str, list[str]] = Field(default_factory=dict)

class ClarifyDecision(BaseModel):
    clarifying_question: str
    reason: str

class StepInput(BaseModel):
    source: str = Field(description="dataset_1 or step_1; only earlier steps.")
    columns: list[str] = Field(default_factory=list)

class ExpectedOutput(BaseModel):
    type: Literal["table", "scalar", "chart"]
    columns: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    row_count: int | None = Field(default=None, ge=0, description="Exact TABLE output row count only when guaranteed; otherwise null. Null for scalar/chart.")
    non_null_columns: list[str] = Field(default_factory=list, description="Subset of this output's columns guaranteed non-null. Never input column names. Empty for scalar/chart.")
    unique_columns: list[str] = Field(default_factory=list, description="Composite unique key of this TABLE output, using only names in columns. Empty when not guaranteed or for scalar/chart.")

class PlanStep(BaseModel):
    engine: Literal["python", "duckdb_sql", "postgres_sql"] = "python"
    step: int = Field(ge=1)
    goal: str = Field(min_length=1)
    inputs: list[StepInput] = Field(min_length=1)
    operation: str = Field(min_length=1)
    expected_output: ExpectedOutput

class AnalysisPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list, max_length=PLAN_MAX_STEPS)
    success_criteria: list[str] = Field(default_factory=list)
    clarification_question: str | None = None

    @model_validator(mode="after")
    def ready_or_question(self):
        if self.clarification_question:
            if self.steps:
                raise ValueError("Clarification must not include executable steps.")
        elif not self.steps or not self.success_criteria:
            raise ValueError("A ready plan requires steps and success criteria.")
        return self

class CodeOutput(BaseModel):
    code: str = Field(min_length=1)

class SyntheticOutput(BaseModel):
    final_answer: str = Field(min_length=1)

class VerificationCheck(BaseModel):
    requirement: str
    status: Literal["pass", "fail", "unknown"]
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str

class VerificationResult(BaseModel):
    decision: Literal["pass", "revise_answer", "replan", "clarify"]
    checks: list[VerificationCheck] = Field(min_length=1)
    feedback: str
    clarification_question: str | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.decision == "pass" and any(
            c.status != "pass" or not c.evidence_refs for c in self.checks
        ):
            raise ValueError("Pass requires supported passing checks.")
        if self.decision == "clarify" and not self.clarification_question:
            raise ValueError("Clarify requires a question.")
        return self

class DataAgentState(TypedDict, total=False):
    schema_version: int
    source_refs: list[str]
    principal: str
    route: str
    analysis_request: str
    analysis_memory: str
    analysis_columns: dict[str, list[str]]
    metrics: list[dict]
    token_charge: int
    deadline: float
    messages: Required[Annotated[list[BaseMessage], add_messages]]
    file_paths: list[str]
    profiles: list[dict]
    profile_summary: str
    profile_cache_key: str
    profile_valid: bool
    profile_errors: list[str]
    plan: dict
    plan_version: int
    current_step_index: int
    step_results: list[dict]
    plan_history: list[dict]
    attempt_history: list[dict]
    code: str | None
    execution_status: Literal["success", "error"] | None
    execution_output: str | None
    execution_error: str | None
    traceback: str | None
    debug_count: int
    replan_count: int
    answer_revision_count: int
    replan_reason: str | None
    verification: dict | None
    draft_answer: str | None
    clarification_question: str | None
    artifact_run_id: str
    artifacts_dir: str
    artifacts: list[str]
    execution_timeout_seconds: int
    final_answer: str | None
    workflow_status: Literal["running", "success", "needs_input", "failed"]
    node_error: str | None
    termination_reason: str | None
