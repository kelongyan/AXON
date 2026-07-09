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


class EvaluationCaseCreate(TrimmedTextModel):
    name: str = Field(min_length=1, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)


class EvaluationCreate(TrimmedTextModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    workflow_id: UUID
    settings: dict[str, Any] = Field(default_factory=dict)
    cases: list[EvaluationCaseCreate] = Field(min_length=1)


class EvaluationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    evaluation_id: UUID
    ordinal: int
    name: str
    input: dict[str, Any]
    expected: dict[str, Any]
    created_at: datetime


class EvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    evaluation_id: UUID
    case_id: UUID
    run_id: UUID | None
    status: str
    output: dict[str, Any] | None
    error_message: str | None
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    created_at: datetime


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    workflow_id: UUID
    name: str
    description: str
    status: str
    settings: dict[str, Any]
    summary: dict[str, Any]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    cases: list[EvaluationCaseResponse] = Field(default_factory=list)
    results: list[EvaluationResultResponse] = Field(default_factory=list)


class EvaluationListResponse(BaseModel):
    items: list[EvaluationResponse]
