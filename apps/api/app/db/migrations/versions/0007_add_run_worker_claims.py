"""add run worker claims

Revision ID: 0007_run_worker_claims
Revises: 0006_phase6_governance
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_run_worker_claims"
down_revision: str | None = "0006_phase6_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("worker_id", sa.String(length=160), nullable=True))
    op.add_column("runs", sa.Column("claim_token", sa.String(length=80), nullable=True))
    op.add_column("runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("current_node_id", sa.String(length=160), nullable=True))
    op.create_index("ix_runs_worker_claim", "runs", ["worker_id", "claim_token"])
    op.create_index("ix_runs_lease_expires", "runs", ["lease_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_runs_lease_expires", table_name="runs")
    op.drop_index("ix_runs_worker_claim", table_name="runs")
    op.drop_column("runs", "current_node_id")
    op.drop_column("runs", "lease_expires_at")
    op.drop_column("runs", "claim_token")
    op.drop_column("runs", "worker_id")
