"""Add renderer_version to presentation_exports for cache invalidation.

When the slide-export-service renderer changes (template CSS, fonts, etc.),
bumping renderer_version automatically invalidates stale cached exports.

Revision ID: 030
Revises: 029
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presentation_exports",
        sa.Column("renderer_version", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("presentation_exports", "renderer_version")
