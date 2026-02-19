"""Add email_draft_bundles table for chat-to-email suggestions.

Revision ID: 017
Revises: 016
Create Date: 2026-02-19

Stores server-side context bundles created by the suggestEmail tool.
The email composer fetches a bundle by ID to hydrate the compose form.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_draft_bundles",
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("body_draft", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_email_draft_bundles_tenant_id",
        "email_draft_bundles",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_draft_bundles_tenant_id", table_name="email_draft_bundles")
    op.drop_table("email_draft_bundles")
