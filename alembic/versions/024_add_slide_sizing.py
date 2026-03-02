"""Add sizing column to presentation_slides for adaptive font/spacing.

Revision ID: 024
Revises: 023
Create Date: 2026-03-01

Stores per-slide sizing hints (font_scale, block_spacing, card_width)
computed by the composer based on template density.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presentation_slides",
        sa.Column("sizing", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("presentation_slides", "sizing")
