"""create phase1 agent tables

Revision ID: 0002_create_phase1_agent_tables
Revises: 0001_create_app_metadata
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_phase1_agent_tables"
down_revision: str | None = "0001_create_app_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.create_index("ix_agents_workspace_status", "agents", ["workspace_id", "status"])
    op.create_index("ix_agents_workspace_created", "agents", ["workspace_id", "created_at"])

    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("role_prompt", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("temperature", sa.Numeric(4, 2), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("tool_ids_snapshot", sa.JSON(), nullable=False),
        sa.Column("knowledge_base_ids_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version_number", name="uq_agent_versions_agent_number"),
    )
    op.create_index("ix_agent_versions_agent", "agent_versions", ["agent_id"])
    op.create_foreign_key(
        "fk_agents_current_version_id",
        "agents",
        "agent_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_calls_agent_id", "llm_calls", ["agent_id"])
    op.create_index("ix_llm_calls_workspace_id", "llm_calls", ["workspace_id"])
    op.create_index("ix_llm_calls_agent_created", "llm_calls", ["agent_id", "created_at"])
    op.create_index("ix_llm_calls_workspace_created", "llm_calls", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_workspace_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_agent_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_workspace_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_agent_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_constraint("fk_agents_current_version_id", "agents", type_="foreignkey")
    op.drop_index("ix_agent_versions_agent", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.drop_index("ix_agents_workspace_created", table_name="agents")
    op.drop_index("ix_agents_workspace_status", table_name="agents")
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_table("agents")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")

