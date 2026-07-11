from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tools import ToolCallResponse


class TrimmedTextModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class WorkflowCreate(TrimmedTextModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class WorkflowVersionCreate(BaseModel):
    graph: dict[str, Any]


class RunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    version_number: int
    graph: dict[str, Any]
    node_snapshots: dict[str, Any]
    referenced_agent_versions: list[str]
    referenced_tool_versions: list[dict[str, Any]]
    status: str
    published_at: datetime


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str
    status: str
    current_version_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    current_version: WorkflowVersionResponse | None = None


class WorkflowDetailResponse(WorkflowResponse):
    versions: list[WorkflowVersionResponse]


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]


class RunStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    run_id: UUID
    node_id: str
    node_type: str
    node_name: str
    status: str
    attempt: int
    input: dict[str, Any]
    output: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class RunLLMCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    run_id: UUID | None
    run_step_id: UUID | None
    provider: str
    model: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    error_message: str | None
    created_at: datetime


class TraceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    run_id: UUID
    run_step_id: UUID | None
    event_type: str
    severity: str
    actor_type: str
    actor_id: str | None
    message: str
    payload: dict[str, Any]
    created_at: datetime


class ApprovalDecisionRequest(TrimmedTextModel):
    comment: str = ""


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    run_id: UUID
    run_step_id: UUID
    node_id: str
    node_name: str
    title: str
    instructions: str
    risk_level: str
    status: str
    requested_payload: dict[str, Any]
    decision: str | None
    decision_comment: str
    decided_by: UUID | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    workflow_id: UUID
    workflow_version_id: UUID
    triggered_by: UUID
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    steps: list[RunStepResponse] = Field(default_factory=list)
    llm_calls: list[RunLLMCallResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallResponse] = Field(default_factory=list)
    trace_events: list[TraceEventResponse] = Field(default_factory=list)
    approvals: list[ApprovalResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    items: list[RunResponse]


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]
