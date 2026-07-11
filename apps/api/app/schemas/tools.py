from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrimmedTextModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ToolCreate(TrimmedTextModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=160)
    description: str = ""
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    risk_level: str = Field(
        pattern="^(read_only|internal_read|low_write|external_effect|sensitive_data|destructive|high_cost)$"
    )
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    requires_approval: bool = False
    status: str = Field(default="active", pattern="^(active|disabled)$")


class ToolGrantRequest(BaseModel):
    policy: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeRequest(BaseModel):
    agent_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    display_name: str
    description: str
    version: str
    risk_level: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: int
    requires_approval: bool
    status: str
    created_at: datetime
    updated_at: datetime


class ToolListResponse(BaseModel):
    items: list[ToolResponse]


class ToolSeedResponse(BaseModel):
    created: int
    updated: int
    items: list[ToolResponse]


class AgentToolResponse(BaseModel):
    agent_id: UUID
    tool_id: UUID
    granted_by: UUID
    granted_at: datetime
    policy: dict[str, Any]


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    tool_id: UUID
    run_id: UUID | None
    run_step_id: UUID | None
    tool_name: str
    status: str
    risk_level: str
    input_summary: dict[str, Any]
    output_summary: dict[str, Any] | None
    latency_ms: int
    error_message: str | None
    created_at: datetime


class ToolCallListResponse(BaseModel):
    items: list[ToolCallResponse]


class ToolInvokeResponse(BaseModel):
    status: str
    output: dict[str, Any] | None
    tool_call: ToolCallResponse

