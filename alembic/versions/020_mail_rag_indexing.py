"""Add email RAG indexing support.

Revision ID: 020
Revises: 019
Create Date: 2026-02-22

- mail_messages: add is_indexed boolean for tracking RAG indexing
- chunks: add source_type/source_id for multi-source chunks, make document_id nullable
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mail_messages: add is_indexed flag
    op.add_column(
        "mail_messages",
        sa.Column("is_indexed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        "ix_mail_messages_not_indexed",
        "mail_messages",
        ["is_indexed"],
        postgresql_where=sa.text("is_indexed = false"),
    )

    # 2. chunks: add source_type and source_id
    op.add_column(
        "chunks",
        sa.Column("source_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column("source_id", PGUUID(as_uuid=True), nullable=True),
    )

    # 3. chunks: make document_id nullable (email chunks have no document)
    op.alter_column("chunks", "document_id", existing_type=PGUUID(as_uuid=True), nullable=True)

    # 4. Index for source-based queries
    op.create_index("ix_chunks_source", "chunks", ["source_type", "source_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_source", table_name="chunks")
    op.alter_column("chunks", "document_id", existing_type=PGUUID(as_uuid=True), nullable=False)
    op.drop_column("chunks", "source_id")
    op.drop_column("chunks", "source_type")
    op.drop_index("ix_mail_messages_not_indexed", table_name="mail_messages")
    op.drop_column("mail_messages", "is_indexed")
