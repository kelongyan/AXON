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


class KnowledgeBaseCreate(TrimmedTextModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    embedding_provider: str = Field(default="openai_compatible", min_length=1, max_length=80)
    embedding_model: str | None = Field(default=None, max_length=160)
    settings: dict[str, Any] = Field(default_factory=dict)


class DocumentCreate(TrimmedTextModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="text/plain", min_length=1, max_length=120)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(TrimmedTextModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[UUID] | None = None


class SourceMetadata(BaseModel):
    knowledge_base_id: UUID
    document_id: UUID
    chunk_id: UUID
    filename: str
    ordinal: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunkResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    knowledge_base_id: UUID
    document_id: UUID
    ordinal: int
    content: str
    token_count: int
    char_count: int
    metadata: dict[str, Any]
    source: SourceMetadata
    created_at: datetime


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    content: str
    score: float
    source: SourceMetadata


class RetrievalResponse(BaseModel):
    query: str
    results: list[RetrievalResult]


class DocumentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str
    source_type: str
    object_key: str
    status: str
    parsing_error: str | None
    text_char_count: int
    chunk_count: int
    metadata: dict[str, Any]
    created_at: datetime
    processed_at: datetime | None


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str
    embedding_provider: str
    embedding_model: str
    status: str
    settings: dict[str, Any]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    chunk_count: int = 0


class KnowledgeBaseDetailResponse(KnowledgeBaseResponse):
    documents: list[DocumentResponse] = Field(default_factory=list)
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
