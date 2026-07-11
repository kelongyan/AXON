from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_column() -> Mapped[UUID]:
    return mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_column()
    email: Mapped[str | None] = mapped_column(sa.String(320), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = uuid_column()
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="active")
    settings: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),)

    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        sa.Index("ix_agents_workspace_status", "workspace_id", "status"),
        sa.Index("ix_agents_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="active")
    current_version_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agent_versions.id", name="fk_agents_current_version_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        sa.UniqueConstraint("agent_id", "version_number", name="uq_agent_versions_agent_number"),
        sa.Index("ix_agent_versions_agent", "agent_id"),
    )

    id: Mapped[UUID] = uuid_column()
    agent_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    role_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    temperature: Mapped[float] = mapped_column(sa.Numeric(4, 2), nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    output_schema: Mapped[dict[str, object] | None] = mapped_column(sa.JSON, nullable=True)
    tool_ids_snapshot: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, default=list)
    knowledge_base_ids_snapshot: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="published")
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class LLMCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        sa.Index("ix_llm_calls_agent_created", "agent_id", "created_at"),
        sa.Index("ix_llm_calls_workspace_created", "workspace_id", "created_at"),
        sa.Index("ix_llm_calls_run_created", "run_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_step_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("run_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    model: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = (
        sa.UniqueConstraint("workspace_id", "name", name="uq_tools_workspace_name"),
        sa.Index("ix_tools_workspace_status", "workspace_id", "status"),
        sa.Index("ix_tools_workspace_risk", "workspace_id", "risk_level"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="1.0.0")
    risk_level: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    input_schema: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    output_schema: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=30)
    requires_approval: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class AgentTool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (
        sa.UniqueConstraint("agent_id", "tool_id", name="uq_agent_tools_agent_tool"),
        sa.Index("ix_agent_tools_tool", "tool_id"),
    )

    agent_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    granted_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    policy: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        sa.UniqueConstraint("workspace_id", "name", name="uq_knowledge_bases_workspace_name"),
        sa.Index("ix_knowledge_bases_workspace_status", "workspace_id", "status"),
        sa.Index("ix_knowledge_bases_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    embedding_provider: Mapped[str] = mapped_column(sa.String(80), nullable=False, default="openai_compatible")
    embedding_model: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="active")
    settings: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("ix_documents_workspace_status", "workspace_id", "status"),
        sa.Index("ix_documents_kb_status", "knowledge_base_id", "status"),
        sa.Index("ix_documents_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="text")
    object_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="uploaded")
    parsing_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    text_char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    source_metadata: Mapped[dict[str, object]] = mapped_column("metadata", sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    processed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunks_document_ordinal"),
        sa.Index("ix_document_chunks_workspace_kb", "workspace_id", "knowledge_base_id"),
        sa.Index("ix_document_chunks_document", "document_id"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    token_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    embedding: Mapped[list[float]] = mapped_column(sa.JSON, nullable=False, default=list)
    source_metadata: Mapped[dict[str, object]] = mapped_column("metadata", sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        sa.Index("ix_tool_calls_workspace_created", "workspace_id", "created_at"),
        sa.Index("ix_tool_calls_agent_created", "agent_id", "created_at"),
        sa.Index("ix_tool_calls_tool_created", "tool_id", "created_at"),
        sa.Index("ix_tool_calls_run_created", "run_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_step_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("run_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    input_summary: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    output_summary: Mapped[dict[str, object] | None] = mapped_column(sa.JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        sa.Index("ix_workflows_workspace_status", "workspace_id", "status"),
        sa.Index("ix_workflows_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="draft")
    current_version_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workflow_versions.id", name="fk_workflows_current_version_id"),
        nullable=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_number"),
        sa.Index("ix_workflow_versions_workflow", "workflow_id"),
    )

    id: Mapped[UUID] = uuid_column()
    workflow_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    graph: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False)
    node_snapshots: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    referenced_agent_versions: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, default=list)
    referenced_tool_versions: Mapped[list[dict[str, object]]] = mapped_column(sa.JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="published")
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        sa.Index("ix_runs_workspace_status", "workspace_id", "status"),
        sa.Index("ix_runs_workflow_created", "workflow_id", "created_at"),
        sa.Index("ix_runs_version_created", "workflow_version_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending")
    worker_id: Mapped[str | None] = mapped_column(sa.String(160), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    current_node_id: Mapped[str | None] = mapped_column(sa.String(160), nullable=True)
    input: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    output: Mapped[dict[str, object] | None] = mapped_column(sa.JSON, nullable=True)
    state: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    error_type: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class RunStep(Base):
    __tablename__ = "run_steps"
    __table_args__ = (
        sa.UniqueConstraint("run_id", "node_id", "attempt", name="uq_run_steps_run_node_attempt"),
        sa.Index("ix_run_steps_run_started", "run_id", "started_at"),
        sa.Index("ix_run_steps_run_status", "run_id", "status"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    node_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    node_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    input: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    output: Mapped[dict[str, object] | None] = mapped_column(sa.JSON, nullable=True)
    error_type: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        sa.Index("ix_approvals_workspace_status", "workspace_id", "status"),
        sa.Index("ix_approvals_run_status", "run_id", "status"),
        sa.Index("ix_approvals_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_step_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("run_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    node_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    instructions: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending")
    requested_payload: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    decision: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    decision_comment: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    decided_by: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        sa.Index("ix_evaluations_workspace_status", "workspace_id", "status"),
        sa.Index("ix_evaluations_workflow_created", "workflow_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="draft")
    settings: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    summary: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_by: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        sa.UniqueConstraint("evaluation_id", "ordinal", name="uq_evaluation_cases_eval_ordinal"),
        sa.Index("ix_evaluation_cases_evaluation", "evaluation_id"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    input: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    expected: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        sa.Index("ix_evaluation_results_evaluation", "evaluation_id"),
        sa.Index("ix_evaluation_results_case_created", "case_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("evaluation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    output: Mapped[dict[str, object] | None] = mapped_column(sa.JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class TraceEvent(Base):
    __tablename__ = "trace_events"
    __table_args__ = (
        sa.Index("ix_trace_events_run_created", "run_id", "created_at"),
        sa.Index("ix_trace_events_workspace_type_created", "workspace_id", "event_type", "created_at"),
        sa.Index("ix_trace_events_step_created", "run_step_id", "created_at"),
    )

    id: Mapped[UUID] = uuid_column()
    workspace_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_step_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("run_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="info")
    actor_type: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(sa.String(160), nullable=True)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
