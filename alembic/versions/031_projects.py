"""Add projects, project_documents, project_knowledge tables.

Add project_id to chunks and conversations.
Update CHECK constraints for three-way scope (org/personal/project).
Add partial composite index for FTS performance.

Revision ID: 031
Revises: 030
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. projects table ──────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
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
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # ── 2. project_documents table ─────────────────────────────────
    op.create_table(
        "project_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
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
    op.create_index(
        "ix_project_documents_project_id", "project_documents", ["project_id"]
    )
    op.create_index(
        "ix_project_documents_user_id", "project_documents", ["user_id"]
    )
    op.create_index(
        "ix_project_documents_tenant_id", "project_documents", ["tenant_id"]
    )
    op.create_index(
        "ix_project_documents_content_hash",
        "project_documents",
        ["content_hash"],
    )
    op.create_index(
        "ix_project_documents_status", "project_documents", ["status"]
    )

    # ── 3. project_knowledge table ─────────────────────────────────
    op.create_table(
        "project_knowledge",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_project_knowledge_project_id", "project_knowledge", ["project_id"]
    )
    op.create_index(
        "ix_project_knowledge_tenant_id", "project_knowledge", ["tenant_id"]
    )

    # ── 4. Add project columns to chunks ───────────────────────────
    op.add_column(
        "chunks",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_chunks_project_id", "chunks", ["project_id"])

    op.add_column(
        "chunks",
        sa.Column(
            "project_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_chunks_project_document_id", "chunks", ["project_document_id"]
    )

    # Partial composite index for FTS performance on project-scope chunks
    op.execute(
        """
        CREATE INDEX ix_chunks_project_scope
        ON chunks (tenant_id, scope, project_id)
        WHERE scope = 'project'
        """
    )

    # ── 5. Add project_id column to conversations ──────────────────
    op.add_column(
        "conversations",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_project_id", "conversations", ["project_id"]
    )

    # ── 6. Update CHECK constraints ────────────────────────────────
    op.drop_constraint("ck_chunks_scope_coherence", "chunks", type_="check")
    op.create_check_constraint(
        "ck_chunks_scope_coherence",
        "chunks",
        """
        (scope = 'org' AND collection_id IS NOT NULL
                      AND user_id IS NULL AND dossier_id IS NULL
                      AND project_id IS NULL)
        OR
        (scope = 'personal' AND user_id IS NOT NULL AND dossier_id IS NOT NULL
                            AND collection_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL AND user_id IS NOT NULL
                           AND collection_id IS NULL AND dossier_id IS NULL)
        """,
    )

    op.drop_constraint(
        "ck_conversations_scope_coherence", "conversations", type_="check"
    )
    op.create_check_constraint(
        "ck_conversations_scope_coherence",
        "conversations",
        """
        (scope = 'org' AND assistant_id IS NOT NULL
                       AND dossier_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'personal' AND dossier_id IS NOT NULL
                            AND assistant_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL
                           AND assistant_id IS NULL AND dossier_id IS NULL)
        """,
    )


def downgrade() -> None:
    # Restore old CHECK constraints
    op.drop_constraint(
        "ck_conversations_scope_coherence", "conversations", type_="check"
    )
    op.create_check_constraint(
        "ck_conversations_scope_coherence",
        "conversations",
        """
        (scope = 'org' AND assistant_id IS NOT NULL AND dossier_id IS NULL)
        OR
        (scope = 'personal' AND dossier_id IS NOT NULL AND assistant_id IS NULL)
        """,
    )

    op.drop_constraint("ck_chunks_scope_coherence", "chunks", type_="check")
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

    # Drop columns
    op.drop_index("ix_conversations_project_id", "conversations")
    op.drop_column("conversations", "project_id")

    op.execute("DROP INDEX IF EXISTS ix_chunks_project_scope")
    op.drop_index("ix_chunks_project_document_id", "chunks")
    op.drop_column("chunks", "project_document_id")
    op.drop_index("ix_chunks_project_id", "chunks")
    op.drop_column("chunks", "project_id")

    # Drop tables
    op.drop_table("project_knowledge")
    op.drop_table("project_documents")
    op.drop_table("projects")
