"""Add blocks JSONB column to messages for Generative UI.

Revision ID: 004_add_blocks_to_messages
Revises: 003
Create Date: 2026-02-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("blocks", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "blocks")
