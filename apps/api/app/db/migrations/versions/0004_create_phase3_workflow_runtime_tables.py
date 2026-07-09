"""create phase3 workflow runtime tables

Revision ID: 0004_phase3_runtime
Revises: 0003_create_phase2_tool_tables
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_phase3_runtime"
down_revision: str | None = "0003_create_phase2_tool_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflows_workspace_id", "workflows", ["workspace_id"])
    op.create_index("ix_workflows_workspace_status", "workflows", ["workspace_id", "status"])
    op.create_index("ix_workflows_workspace_created", "workflows", ["workspace_id", "created_at"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("node_snapshots", sa.JSON(), nullable=False),
        sa.Column("referenced_agent_versions", sa.JSON(), nullable=False),
        sa.Column("referenced_tool_versions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_number"),
    )
    op.create_index("ix_workflow_versions_workflow", "workflow_versions", ["workflow_id"])
    op.create_foreign_key(
        "fk_workflows_current_version_id",
        "workflows",
        "workflow_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_workspace_id", "runs", ["workspace_id"])
    op.create_index("ix_runs_workflow_id", "runs", ["workflow_id"])
    op.create_index("ix_runs_workflow_version_id", "runs", ["workflow_version_id"])
    op.create_index("ix_runs_workspace_status", "runs", ["workspace_id", "status"])
    op.create_index("ix_runs_workflow_created", "runs", ["workflow_id", "created_at"])
    op.create_index("ix_runs_version_created", "runs", ["workflow_version_id", "created_at"])

    op.create_table(
        "run_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.String(length=160), nullable=False),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("node_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "node_id", "attempt", name="uq_run_steps_run_node_attempt"),
    )
    op.create_index("ix_run_steps_workspace_id", "run_steps", ["workspace_id"])
    op.create_index("ix_run_steps_run_id", "run_steps", ["run_id"])
    op.create_index("ix_run_steps_run_started", "run_steps", ["run_id", "started_at"])
    op.create_index("ix_run_steps_run_status", "run_steps", ["run_id", "status"])

    op.create_table(
        "trace_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("run_step_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_step_id"], ["run_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trace_events_workspace_id", "trace_events", ["workspace_id"])
    op.create_index("ix_trace_events_run_id", "trace_events", ["run_id"])
    op.create_index("ix_trace_events_run_step_id", "trace_events", ["run_step_id"])
    op.create_index("ix_trace_events_run_created", "trace_events", ["run_id", "created_at"])
    op.create_index(
        "ix_trace_events_workspace_type_created",
        "trace_events",
        ["workspace_id", "event_type", "created_at"],
    )
    op.create_index("ix_trace_events_step_created", "trace_events", ["run_step_id", "created_at"])

    op.add_column("llm_calls", sa.Column("run_id", sa.Uuid(), nullable=True))
    op.add_column("llm_calls", sa.Column("run_step_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_llm_calls_run_id", "llm_calls", "runs", ["run_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_llm_calls_run_step_id",
        "llm_calls",
        "run_steps",
        ["run_step_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])
    op.create_index("ix_llm_calls_run_step_id", "llm_calls", ["run_step_id"])
    op.create_index("ix_llm_calls_run_created", "llm_calls", ["run_id", "created_at"])

    op.add_column("tool_calls", sa.Column("run_id", sa.Uuid(), nullable=True))
    op.add_column("tool_calls", sa.Column("run_step_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_tool_calls_run_id", "tool_calls", "runs", ["run_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_tool_calls_run_step_id",
        "tool_calls",
        "run_steps",
        ["run_step_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"])
    op.create_index("ix_tool_calls_run_step_id", "tool_calls", ["run_step_id"])
    op.create_index("ix_tool_calls_run_created", "tool_calls", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_run_created", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_step_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_id", table_name="tool_calls")
    op.drop_constraint("fk_tool_calls_run_step_id", "tool_calls", type_="foreignkey")
    op.drop_constraint("fk_tool_calls_run_id", "tool_calls", type_="foreignkey")
    op.drop_column("tool_calls", "run_step_id")
    op.drop_column("tool_calls", "run_id")

    op.drop_index("ix_llm_calls_run_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_run_step_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_constraint("fk_llm_calls_run_step_id", "llm_calls", type_="foreignkey")
    op.drop_constraint("fk_llm_calls_run_id", "llm_calls", type_="foreignkey")
    op.drop_column("llm_calls", "run_step_id")
    op.drop_column("llm_calls", "run_id")

    op.drop_index("ix_trace_events_step_created", table_name="trace_events")
    op.drop_index("ix_trace_events_workspace_type_created", table_name="trace_events")
    op.drop_index("ix_trace_events_run_created", table_name="trace_events")
    op.drop_index("ix_trace_events_run_step_id", table_name="trace_events")
    op.drop_index("ix_trace_events_run_id", table_name="trace_events")
    op.drop_index("ix_trace_events_workspace_id", table_name="trace_events")
    op.drop_table("trace_events")
    op.drop_index("ix_run_steps_run_status", table_name="run_steps")
    op.drop_index("ix_run_steps_run_started", table_name="run_steps")
    op.drop_index("ix_run_steps_run_id", table_name="run_steps")
    op.drop_index("ix_run_steps_workspace_id", table_name="run_steps")
    op.drop_table("run_steps")
    op.drop_index("ix_runs_version_created", table_name="runs")
    op.drop_index("ix_runs_workflow_created", table_name="runs")
    op.drop_index("ix_runs_workspace_status", table_name="runs")
    op.drop_index("ix_runs_workflow_version_id", table_name="runs")
    op.drop_index("ix_runs_workflow_id", table_name="runs")
    op.drop_index("ix_runs_workspace_id", table_name="runs")
    op.drop_table("runs")
    op.drop_constraint("fk_workflows_current_version_id", "workflows", type_="foreignkey")
    op.drop_index("ix_workflow_versions_workflow", table_name="workflow_versions")
    op.drop_table("workflow_versions")
    op.drop_index("ix_workflows_workspace_created", table_name="workflows")
    op.drop_index("ix_workflows_workspace_status", table_name="workflows")
    op.drop_index("ix_workflows_workspace_id", table_name="workflows")
    op.drop_table("workflows")
