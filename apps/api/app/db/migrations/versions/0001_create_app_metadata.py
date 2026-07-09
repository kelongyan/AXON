"""create app metadata

Revision ID: 0001_create_app_metadata
Revises:
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_app_metadata"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_metadata")

