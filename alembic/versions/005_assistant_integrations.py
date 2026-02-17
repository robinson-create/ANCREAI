"""Add assistant_integrations M2M table.

Links assistants to Nango connections (max 2 per assistant, enforced in app).

Revision ID: 005
Revises: 004
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_integrations",
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "nango_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nango_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("assistant_integrations")
