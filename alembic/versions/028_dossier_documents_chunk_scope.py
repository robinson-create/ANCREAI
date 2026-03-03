"""Add dossier_documents table + chunk scope columns.

Creates the dossier_documents table for personal file uploads.
Adds scope, user_id, dossier_id, dossier_document_id columns to chunks
with a CHECK constraint enforcing org/personal coherence.
Backfills existing chunks to scope='org'.

Revision ID: 028
Revises: 027
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Create dossier_documents table ---
    op.create_table(
        "dossier_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dossier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dossiers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), default="pending", index=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("doc_metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- 2. Add scope column to chunks (NOT NULL with default) ---
    op.add_column(
        "chunks",
        sa.Column(
            "scope",
            sa.String(20),
            nullable=False,
            server_default="org",
        ),
    )
    op.create_index("ix_chunks_scope", "chunks", ["scope"])

    # --- 3. Add personal-scope columns to chunks ---
    op.add_column(
        "chunks",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_chunks_user_id", "chunks", ["user_id"])

    op.add_column(
        "chunks",
        sa.Column(
            "dossier_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_chunks_dossier_id", "chunks", ["dossier_id"])

    op.add_column(
        "chunks",
        sa.Column(
            "dossier_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dossier_documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_chunks_dossier_document_id", "chunks", ["dossier_document_id"])

    # --- 4. Backfill existing chunks to scope='org' ---
    op.execute("UPDATE chunks SET scope = 'org' WHERE scope IS NULL OR scope = ''")

    # --- 5. Add CHECK constraint for scope coherence ---
    op.create_check_constraint(
        "ck_chunks_scope_coherence",
        "chunks",
        """
        (scope = 'org' AND collection_id IS NOT NULL
                      AND user_id IS NULL AND dossier_id IS NULL)
        OR
        (scope = 'personal' AND user_id IS NOT NULL AND dossier_id IS NOT NULL
                            AND collection_id IS NULL)
        """,
    )

    # --- 6. Add multi-source columns to chunks (idempotent — may already exist) ---
    op.execute("""
        ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type VARCHAR(20);
    """)
    op.execute("""
        ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_id UUID;
    """)


def downgrade() -> None:
    # Drop CHECK constraint
    op.drop_constraint("ck_chunks_scope_coherence", "chunks", type_="check")

    # Drop new chunk columns
    op.drop_column("chunks", "source_id")
    op.drop_column("chunks", "source_type")

    op.drop_index("ix_chunks_dossier_document_id", table_name="chunks")
    op.drop_column("chunks", "dossier_document_id")

    op.drop_index("ix_chunks_dossier_id", table_name="chunks")
    op.drop_column("chunks", "dossier_id")

    op.drop_index("ix_chunks_user_id", table_name="chunks")
    op.drop_column("chunks", "user_id")

    op.drop_index("ix_chunks_scope", table_name="chunks")
    op.drop_column("chunks", "scope")

    # Drop dossier_documents table
    op.drop_table("dossier_documents")
