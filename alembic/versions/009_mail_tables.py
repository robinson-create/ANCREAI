"""Add mail integration tables.

Revision ID: 009
Revises: 008
Create Date: 2026-02-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── mail_accounts ──
    op.create_table(
        "mail_accounts",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=True),
        sa.Column(
            "nango_conn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nango_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("scopes", postgresql.JSONB(), nullable=True),
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
    op.create_index("ix_mail_accounts_tenant_id", "mail_accounts", ["tenant_id"])
    op.create_index("ix_mail_accounts_user_id", "mail_accounts", ["user_id"])
    op.create_index("ix_mail_accounts_nango_conn_id", "mail_accounts", ["nango_conn_id"])

    # ── mail_messages ──
    op.create_table(
        "mail_messages",
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
        sa.Column("provider_message_id", sa.String(255), nullable=False),
        sa.Column("provider_thread_id", sa.String(255), nullable=True),
        sa.Column("internet_message_id", sa.String(500), nullable=True),
        sa.Column("sender", postgresql.JSONB(), nullable=False),
        sa.Column("to_recipients", postgresql.JSONB(), nullable=False),
        sa.Column("cc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("bcc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_draft", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("has_attachments", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("raw_headers", postgresql.JSONB(), nullable=True),
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
    op.create_index("ix_mail_messages_tenant_id", "mail_messages", ["tenant_id"])
    op.create_index("ix_mail_messages_account_id", "mail_messages", ["mail_account_id"])
    op.create_index(
        "ix_mail_messages_thread", "mail_messages", ["mail_account_id", "provider_thread_id"]
    )
    op.create_index(
        "ix_mail_messages_date", "mail_messages", ["mail_account_id", "date"]
    )
    op.create_unique_constraint(
        "uq_mail_msg_account_provider",
        "mail_messages",
        ["mail_account_id", "provider_message_id"],
    )

    # ── mail_sync_state ──
    op.create_table(
        "mail_sync_state",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "mail_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("gmail_history_id", sa.String(50), nullable=True),
        sa.Column("graph_delta_link", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="idle"
        ),
        sa.Column("error", sa.Text(), nullable=True),
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

    # ── mail_send_requests ──
    op.create_table(
        "mail_send_requests",
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
            "client_send_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("to_recipients", postgresql.JSONB(), nullable=False),
        sa.Column("cc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("bcc_recipients", postgresql.JSONB(), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column(
            "in_reply_to_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_thread_id", sa.String(255), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="queued"
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_mail_send_requests_tenant_id", "mail_send_requests", ["tenant_id"]
    )
    op.create_index(
        "ix_mail_send_requests_account_id", "mail_send_requests", ["mail_account_id"]
    )
    op.create_unique_constraint(
        "uq_send_tenant_client",
        "mail_send_requests",
        ["tenant_id", "client_send_id"],
    )


def downgrade() -> None:
    op.drop_table("mail_send_requests")
    op.drop_table("mail_sync_state")
    op.drop_table("mail_messages")
    op.drop_table("mail_accounts")
