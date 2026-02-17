"""Add SMTP config for mail_accounts.

Revision ID: 014
Revises: 013
Create Date: 2026-02-17

Adds smtp_config JSONB column to mail_accounts for SMTP-based connections
(Gmail SMTP, Outlook SMTP, or custom SMTP servers).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mail_accounts",
        sa.Column(
            "smtp_config",
            postgresql.JSONB(),
            nullable=True,
            comment='{"host": "...", "port": 587, "user": "...", "password_encrypted": "...", "use_tls": true}',
        ),
    )


def downgrade() -> None:
    op.drop_column("mail_accounts", "smtp_config")
