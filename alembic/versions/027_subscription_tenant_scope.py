"""Add tenant_id + seat/assistant limits to subscriptions.

Transition migration: adds tenant_id as a new column (nullable) and
backfills it from users.tenant_id.  Also adds max_seats, max_assistants,
max_org_documents columns with free-tier defaults.

Revision ID: 027
Revises: 026
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Add tenant_id column (nullable during transition) ---
    op.add_column(
        "subscriptions",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"], unique=True)

    # --- 2. Backfill tenant_id from users.tenant_id ---
    op.execute(
        """
        UPDATE subscriptions s
        SET tenant_id = u.tenant_id
        FROM users u
        WHERE s.user_id = u.id
          AND s.tenant_id IS NULL
        """
    )

    # --- 3. Add seat & assistant limit columns ---
    op.add_column(
        "subscriptions",
        sa.Column("max_seats", sa.Integer, server_default="1", nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("max_assistants", sa.Integer, server_default="1", nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("max_org_documents", sa.Integer, server_default="10", nullable=False),
    )

    # --- 4. Set Pro subscriptions to higher limits ---
    op.execute(
        """
        UPDATE subscriptions
        SET max_seats = 3,
            max_assistants = 3,
            max_org_documents = 999999
        WHERE plan = 'pro'
          AND status IN ('active', 'trialing')
        """
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "max_org_documents")
    op.drop_column("subscriptions", "max_assistants")
    op.drop_column("subscriptions", "max_seats")
    op.drop_index("ix_subscriptions_tenant_id", table_name="subscriptions")
    op.drop_column("subscriptions", "tenant_id")
