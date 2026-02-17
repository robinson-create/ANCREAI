"""Add transcription seconds quota tracking.

Adds a transcription_seconds counter to the usage table and
a max_transcription_seconds limit to the tenants table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage",
        sa.Column("transcription_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("max_transcription_seconds", sa.Integer(), nullable=False, server_default="120"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "max_transcription_seconds")
    op.drop_column("usage", "transcription_seconds")
