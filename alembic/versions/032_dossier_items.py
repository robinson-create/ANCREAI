"""dossier_items table for generic item linking

Revision ID: 032
Revises: 031
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dossier_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dossier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dossiers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("item_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "dossier_id",
            "item_type",
            "item_id",
            name="uq_dossier_items_dossier_type_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("dossier_items")
