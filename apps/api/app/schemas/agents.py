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


class AgentVersionCreate(TrimmedTextModel):
    role_prompt: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    model_provider: str = Field(default="openai_compatible", min_length=1, max_length=80)
    model_name: str = Field(min_length=1, max_length=160)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=1000, ge=1, le=32000)
    output_schema: dict[str, Any] | None = None
    knowledge_base_ids: list[UUID] = Field(default_factory=list)


class AgentCreate(AgentVersionCreate):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class AgentUpdate(TrimmedTextModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|disabled)$")


class AgentTestRunRequest(TrimmedTextModel):
    input: str = Field(min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str
    avatar_url: str | None
    status: str


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: str


class MembershipResponse(BaseModel):
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
    membership: MembershipResponse


class AgentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    version_number: int
    role_prompt: str
    system_prompt: str
    model_provider: str
    model_name: str
    temperature: float
    max_output_tokens: int
    output_schema: dict[str, Any] | None
    knowledge_base_ids_snapshot: list[str]
    status: str
    published_at: datetime


class LLMCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    provider: str
    model: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    error_message: str | None
    created_at: datetime


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str
    status: str
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime
    current_version: AgentVersionResponse | None


class AgentDetailResponse(AgentResponse):
    versions: list[AgentVersionResponse]
    recent_llm_calls: list[LLMCallResponse]


class AgentListResponse(BaseModel):
    items: list[AgentResponse]


class AgentTestRunResponse(BaseModel):
    output: str
    llm_call: LLMCallResponse
