"""create phase6 governance tables

Revision ID: 0006_phase6_governance
Revises: 0005_phase4_rag
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_phase6_governance"
down_revision: str | None = "0005_phase4_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("run_step_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.String(length=160), nullable=False),
        sa.Column("node_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_payload", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_step_id"], ["run_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_workspace_id", "approvals", ["workspace_id"])
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])
    op.create_index("ix_approvals_run_step_id", "approvals", ["run_step_id"])
    op.create_index("ix_approvals_workspace_status", "approvals", ["workspace_id", "status"])
    op.create_index("ix_approvals_run_status", "approvals", ["run_id", "status"])
    op.create_index("ix_approvals_workspace_created", "approvals", ["workspace_id", "created_at"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluations_workspace_id", "evaluations", ["workspace_id"])
    op.create_index("ix_evaluations_workflow_id", "evaluations", ["workflow_id"])
    op.create_index("ix_evaluations_workspace_status", "evaluations", ["workspace_id", "status"])
    op.create_index("ix_evaluations_workflow_created", "evaluations", ["workflow_id", "created_at"])

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "ordinal", name="uq_evaluation_cases_eval_ordinal"),
    )
    op.create_index("ix_evaluation_cases_workspace_id", "evaluation_cases", ["workspace_id"])
    op.create_index("ix_evaluation_cases_evaluation_id", "evaluation_cases", ["evaluation_id"])
    op.create_index("ix_evaluation_cases_evaluation", "evaluation_cases", ["evaluation_id"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["evaluation_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_results_workspace_id", "evaluation_results", ["workspace_id"])
    op.create_index("ix_evaluation_results_evaluation_id", "evaluation_results", ["evaluation_id"])
    op.create_index("ix_evaluation_results_case_id", "evaluation_results", ["case_id"])
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"])
    op.create_index("ix_evaluation_results_evaluation", "evaluation_results", ["evaluation_id"])
    op.create_index("ix_evaluation_results_case_created", "evaluation_results", ["case_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_case_created", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_evaluation", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_run_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_evaluation_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_workspace_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_evaluation_cases_evaluation", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_evaluation_id", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_workspace_id", table_name="evaluation_cases")
    op.drop_table("evaluation_cases")
    op.drop_index("ix_evaluations_workflow_created", table_name="evaluations")
    op.drop_index("ix_evaluations_workspace_status", table_name="evaluations")
    op.drop_index("ix_evaluations_workflow_id", table_name="evaluations")
    op.drop_index("ix_evaluations_workspace_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_approvals_workspace_created", table_name="approvals")
    op.drop_index("ix_approvals_run_status", table_name="approvals")
    op.drop_index("ix_approvals_workspace_status", table_name="approvals")
    op.drop_index("ix_approvals_run_step_id", table_name="approvals")
    op.drop_index("ix_approvals_run_id", table_name="approvals")
    op.drop_index("ix_approvals_workspace_id", table_name="approvals")
    op.drop_table("approvals")
