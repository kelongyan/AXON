"""create phase4 rag knowledge base tables

Revision ID: 0005_phase4_rag
Revises: 0004_phase3_runtime
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_phase4_rag"
down_revision: str | None = "0004_phase3_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=80), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_knowledge_bases_workspace_name"),
    )
    op.create_index("ix_knowledge_bases_workspace_id", "knowledge_bases", ["workspace_id"])
    op.create_index("ix_knowledge_bases_workspace_status", "knowledge_bases", ["workspace_id", "status"])
    op.create_index("ix_knowledge_bases_workspace_created", "knowledge_bases", ["workspace_id", "created_at"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("object_key", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("text_char_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    op.create_index("ix_documents_workspace_status", "documents", ["workspace_id", "status"])
    op.create_index("ix_documents_kb_status", "documents", ["knowledge_base_id", "status"])
    op.create_index("ix_documents_workspace_created", "documents", ["workspace_id", "created_at"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunks_document_ordinal"),
    )
    op.create_index("ix_document_chunks_workspace_id", "document_chunks", ["workspace_id"])
    op.create_index("ix_document_chunks_knowledge_base_id", "document_chunks", ["knowledge_base_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_workspace_kb", "document_chunks", ["workspace_id", "knowledge_base_id"])
    op.create_index("ix_document_chunks_document", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document", table_name="document_chunks")
    op.drop_index("ix_document_chunks_workspace_kb", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_knowledge_base_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_workspace_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_workspace_created", table_name="documents")
    op.drop_index("ix_documents_kb_status", table_name="documents")
    op.drop_index("ix_documents_workspace_status", table_name="documents")
    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_knowledge_bases_workspace_created", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_workspace_status", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_workspace_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
