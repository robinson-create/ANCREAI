"""Initial schema with all tables.

Revision ID: 001
Revises: 
Create Date: 2025-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("settings", postgresql.JSONB, default={}),
        sa.Column("max_assistants", sa.Integer, default=3),
        sa.Column("max_ingestion_tokens", sa.Integer, default=1000000),
        sa.Column("max_chat_tokens", sa.Integer, default=500000),
        sa.Column("max_storage_bytes", sa.Integer, default=1073741824),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Assistants
    op.create_table(
        "assistants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("system_prompt", sa.Text),
        sa.Column("model", sa.String(100), default="gpt-4o-mini"),
        sa.Column("settings", postgresql.JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assistants_tenant_id", "assistants", ["tenant_id"])

    # Collections
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_collections_tenant_id", "collections", ["tenant_id"])

    # Assistant-Collection M2M
    op.create_table(
        "assistant_collections",
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    )

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("error_message", sa.String(2000)),
        sa.Column("page_count", sa.Integer),
        sa.Column("chunk_count", sa.Integer),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("doc_metadata", postgresql.JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_documents_collection_id", "documents", ["collection_id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # Chunks
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer),
        sa.Column("start_offset", sa.Integer),
        sa.Column("end_offset", sa.Integer),
        sa.Column("section_title", sa.String(500)),
        sa.Column("qdrant_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"])
    op.create_index("ix_chunks_qdrant_id", "chunks", ["qdrant_id"])

    # Messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", postgresql.JSONB),
        sa.Column("tokens_input", sa.Integer),
        sa.Column("tokens_output", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_assistant_id", "messages", ["assistant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # Usage
    op.create_table(
        "usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("ingestion_tokens", sa.BigInteger, default=0),
        sa.Column("chat_input_tokens", sa.BigInteger, default=0),
        sa.Column("chat_output_tokens", sa.BigInteger, default=0),
        sa.Column("storage_bytes", sa.BigInteger, default=0),
        sa.Column("documents_count", sa.Integer, default=0),
        sa.Column("messages_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_tenant_id", "usage", ["tenant_id"])
    op.create_unique_constraint("uq_usage_tenant_period", "usage", ["tenant_id", "period"])


def downgrade() -> None:
    op.drop_table("usage")
    op.drop_table("messages")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("assistant_collections")
    op.drop_table("collections")
    op.drop_table("assistants")
    op.drop_table("tenants")
