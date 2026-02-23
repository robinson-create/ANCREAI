"""Add scheduled_emails table for email scheduling.

Revision ID: 022
Revises: 021
Create Date: 2026-02-23

Allows users to schedule emails to be sent at a specific time.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_emails",
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
            "mode",
            sa.String(20),
            nullable=False,
            comment="new | reply | forward",
        ),
        sa.Column(
            "to_recipients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("cc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("bcc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column(
            "in_reply_to_message_id",
            sa.String(255),
            nullable=True,
            comment="Internet-Message-ID for threading",
        ),
        sa.Column(
            "provider_thread_id",
            sa.String(255),
            nullable=True,
            comment="Provider-specific thread ID",
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When to send this email",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending | sent | failed | cancelled",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_scheduled_emails_tenant_id", "scheduled_emails", ["tenant_id"])
    op.create_index("ix_scheduled_emails_mail_account_id", "scheduled_emails", ["mail_account_id"])
    op.create_index("ix_scheduled_emails_scheduled_at", "scheduled_emails", ["scheduled_at"])
    op.create_index("ix_scheduled_emails_scheduled_at_status", "scheduled_emails", ["scheduled_at", "status"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_emails_scheduled_at_status", table_name="scheduled_emails")
    op.drop_index("ix_scheduled_emails_scheduled_at", table_name="scheduled_emails")
    op.drop_index("ix_scheduled_emails_mail_account_id", table_name="scheduled_emails")
    op.drop_index("ix_scheduled_emails_tenant_id", table_name="scheduled_emails")
    op.drop_table("scheduled_emails")
