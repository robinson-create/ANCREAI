"""Add workspace_documents and document_templates tables.

Revision ID: 008
Revises: 007
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── workspace_documents ──
    op.create_table(
        "workspace_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False, server_default="Sans titre"),
        sa.Column("doc_type", sa.String(100), nullable=False, server_default="generic"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("content_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_exported_url", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_workspace_documents_tenant_id", "workspace_documents", ["tenant_id"])
    op.create_index("ix_workspace_documents_assistant_id", "workspace_documents", ["assistant_id"])
    op.create_index("ix_workspace_documents_status", "workspace_documents", ["status"])

    # ── document_templates ──
    op.create_table(
        "document_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=False),
        sa.Column("engine", sa.String(50), nullable=False, server_default="htmlpdf"),
        sa.Column("template_ref", sa.String(500), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(), nullable=True),
        sa.Column("content_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_document_templates_tenant_id", "document_templates", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("document_templates")
    op.drop_table("workspace_documents")
