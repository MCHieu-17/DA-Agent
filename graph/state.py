"""Structured LLM outputs and serializable LangGraph state."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Required, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    intent: Literal["chat", "analysis"]


class AnalysisStep(BaseModel):
    objective: str = Field(description="A short, observable analysis objective.")
    kind: Literal["explore", "query", "visualize", "custom_compute"]
    success_criteria: str = Field(description="What evidence this step must produce.")


class AnalysisPlan(BaseModel):
    assumptions: list[str] = Field(default_factory=list)
    steps: list[AnalysisStep] = Field(default_factory=list)


class ActionDecision(BaseModel):
    mode: Literal["tool", "code"]
    tool_name: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    fallback_reason: Optional[str] = None


class CoderOutput(BaseModel):
    code: str


class ValidatorOutput(BaseModel):
    is_valid: bool
    feedback: str = ""


class SyntheticOutput(BaseModel):
    final_answer: str


class DataAgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    file_paths: list[str]
    artifacts_dir: Required[str]
    final_answer: Optional[str]
    artifacts: list[str]
    schema_str: Optional[str]
    schema_file_paths: Optional[list[str]]
    data_profile: dict[str, Any]
    profile_summary: str
    profile_fingerprints: dict[str, str]
    plan: list[dict[str, Any]]
    current_step_idx: int
    assumptions: list[str]
    action: dict[str, Any]
    past_steps: list[dict[str, Any]]
    execution_records: list[dict[str, Any]]
    code: Optional[str]
    execution_status: Optional[Literal["success", "error"]]
    execution_output: Optional[str]
    execution_error: Optional[str]
    traceback: Optional[str]
    debug_feedback: Optional[str]
    retry_count: int
    tool_retry_count: int
    replan_count: int
    max_retries: int
    max_replans: int
    run_id: str
    sandbox_id: Optional[str]
    sandbox_file_map: dict[str, str]
    is_sufficient: Optional[bool]
    validation_feedback: Optional[str]
