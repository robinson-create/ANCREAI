"""Add hybrid search: FTS columns on chunks + document_pages table.

Revision ID: 007
Revises: 006
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add denormalized columns to chunks for FTS ──
    op.add_column("chunks", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chunks", sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "chunks",
        sa.Column("content_tsv", postgresql.TSVECTOR(), nullable=True),
    )

    # ── 2. Backfill tenant_id and collection_id from document → collection ──
    op.execute(
        """
        UPDATE chunks c
        SET collection_id = d.collection_id,
            tenant_id = col.tenant_id
        FROM documents d
        JOIN collections col ON col.id = d.collection_id
        WHERE c.document_id = d.id
          AND c.tenant_id IS NULL
        """
    )

    # ── 3. Backfill content_tsv ──
    op.execute(
        """
        UPDATE chunks
        SET content_tsv = to_tsvector('simple', content)
        WHERE content_tsv IS NULL
        """
    )

    # ── 4. Indexes ──
    op.create_index(
        "ix_chunks_content_tsv",
        "chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_chunks_tenant_collection",
        "chunks",
        ["tenant_id", "collection_id"],
    )

    # ── 5. Create document_pages table ──
    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
    )
    op.create_index("ix_document_pages_tenant_doc", "document_pages", ["tenant_id", "document_id"])


def downgrade() -> None:
    op.drop_table("document_pages")
    op.drop_index("ix_chunks_tenant_collection", table_name="chunks")
    op.drop_index("ix_chunks_content_tsv", table_name="chunks")
    op.drop_column("chunks", "content_tsv")
    op.drop_column("chunks", "collection_id")
    op.drop_column("chunks", "tenant_id")
