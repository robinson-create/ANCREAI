"""Seed two built-in presentation themes with design tokens.

Revision ID: 025
Revises: 024
Create Date: 2026-03-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSULTING_MODERNE_ID = "00000000-0000-4000-a000-000000000001"
STARTUP_ARTISAN_ID = "00000000-0000-4000-a000-000000000002"

THEMES = [
    {
        "id": CONSULTING_MODERNE_ID,
        "name": "Consulting Moderne",
        "is_builtin": True,
        "tenant_id": None,
        "theme_data": {
            "colors": {
                "primary": "#3B82F6",
                "secondary": "#1E293B",
                "accent": "#10B981",
                "background": "#FFFFFF",
                "text": "#334155",
                "heading": "#0F172A",
                "muted": "#94A3B8",
            },
            "fonts": {"heading": "Inter", "body": "Inter"},
            "border_radius": "12px",
            "design_tokens": {
                "shadow_level": "soft",
                "card_style": "soft-elevated",
                "accent_usage": "balanced",
            },
        },
    },
    {
        "id": STARTUP_ARTISAN_ID,
        "name": "Startup Artisan",
        "is_builtin": True,
        "tenant_id": None,
        "theme_data": {
            "colors": {
                "primary": "#E8732C",
                "secondary": "#2D3748",
                "accent": "#D4A853",
                "background": "#F5F0EB",
                "text": "#2D3748",
                "heading": "#1A202C",
                "muted": "#718096",
            },
            "fonts": {"heading": "Montserrat", "body": "Open Sans"},
            "border_radius": "8px",
            "design_tokens": {
                "shadow_level": "none",
                "card_style": "flat",
                "accent_usage": "strong",
            },
        },
    },
]


def upgrade() -> None:
    themes_table = sa.table(
        "presentation_themes",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("is_builtin", sa.Boolean),
        sa.column("theme_data", postgresql.JSONB),
    )
    for t in THEMES:
        op.execute(
            themes_table.insert().values(
                id=t["id"],
                tenant_id=t["tenant_id"],
                name=t["name"],
                is_builtin=t["is_builtin"],
                theme_data=t["theme_data"],
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM presentation_themes WHERE id IN (:id1, :id2)"
        ).bindparams(id1=CONSULTING_MODERNE_ID, id2=STARTUP_ARTISAN_ID)
    )
