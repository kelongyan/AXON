"""create phase2 tool tables

Revision ID: 0003_create_phase2_tool_tables
Revises: 0002_create_phase1_agent_tables
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_create_phase2_tool_tables"
down_revision: str | None = "0002_create_phase1_agent_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_tools_workspace_name"),
    )
    op.create_index("ix_tools_workspace_id", "tools", ["workspace_id"])
    op.create_index("ix_tools_workspace_status", "tools", ["workspace_id", "status"])
    op.create_index("ix_tools_workspace_risk", "tools", ["workspace_id", "risk_level"])

    op.create_table(
        "agent_tools",
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "tool_id"),
        sa.UniqueConstraint("agent_id", "tool_id", name="uq_agent_tools_agent_tool"),
    )
    op.create_index("ix_agent_tools_tool", "agent_tools", ["tool_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_calls_workspace_id", "tool_calls", ["workspace_id"])
    op.create_index("ix_tool_calls_agent_id", "tool_calls", ["agent_id"])
    op.create_index("ix_tool_calls_tool_id", "tool_calls", ["tool_id"])
    op.create_index("ix_tool_calls_workspace_created", "tool_calls", ["workspace_id", "created_at"])
    op.create_index("ix_tool_calls_agent_created", "tool_calls", ["agent_id", "created_at"])
    op.create_index("ix_tool_calls_tool_created", "tool_calls", ["tool_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_tool_created", table_name="tool_calls")
    op.drop_index("ix_tool_calls_agent_created", table_name="tool_calls")
    op.drop_index("ix_tool_calls_workspace_created", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tool_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_agent_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_workspace_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_agent_tools_tool", table_name="agent_tools")
    op.drop_table("agent_tools")
    op.drop_index("ix_tools_workspace_risk", table_name="tools")
    op.drop_index("ix_tools_workspace_status", table_name="tools")
    op.drop_index("ix_tools_workspace_id", table_name="tools")
    op.drop_table("tools")

