"""Add mail_drafts table for local composer drafts.

Revision ID: 015
Revises: 014
Create Date: 2026-02-17

Drafts saved from the email composer are stored here and visible in the mail list.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mail_drafts",
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
            "mail_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_recipients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_mail_drafts_tenant_id", "mail_drafts", ["tenant_id"])
    op.create_index("ix_mail_drafts_mail_account_id", "mail_drafts", ["mail_account_id"])
    op.create_index("ix_mail_drafts_updated_at", "mail_drafts", ["mail_account_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_mail_drafts_updated_at", table_name="mail_drafts")
    op.drop_index("ix_mail_drafts_mail_account_id", table_name="mail_drafts")
    op.drop_index("ix_mail_drafts_tenant_id", table_name="mail_drafts")
    op.drop_table("mail_drafts")
