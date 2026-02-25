"""Add presentation tables for AI slide generation and export.

Revision ID: 023
Revises: 022
Create Date: 2026-02-25

Tables: presentations, presentation_slides, presentation_themes,
        presentation_assets, presentation_exports, presentation_generation_runs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── presentation_themes (referenced by presentations.theme_id) ──
    op.create_table(
        "presentation_themes",
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
            nullable=True,
            comment="NULL = built-in theme",
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("theme_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_presentation_themes_tenant_id", "presentation_themes", ["tenant_id"])

    # ── presentations ──
    op.create_table(
        "presentations",
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
        sa.Column("title", sa.String(500), nullable=False, server_default=sa.text("'Sans titre'")),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'draft'"),
            comment="draft|generating_outline|outline_ready|generating_slides|ready|exporting|error",
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentation_themes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "outline",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "slide_order",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_presentations_tenant_id", "presentations", ["tenant_id"])
    op.create_index("ix_presentations_status", "presentations", ["status"])
    op.create_index(
        "ix_presentations_tenant_updated",
        "presentations",
        ["tenant_id", "updated_at"],
    )

    # ── presentation_slides ──
    op.create_table(
        "presentation_slides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("layout_type", sa.String(20), server_default=sa.text("'vertical'")),
        sa.Column(
            "content_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("root_image", postgresql.JSONB(), nullable=True),
        sa.Column("bg_color", sa.String(20), nullable=True),
        sa.Column("speaker_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pslides_pres_pos",
        "presentation_slides",
        ["presentation_id", "position"],
    )

    # ── presentation_assets ──
    op.create_table(
        "presentation_assets",
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
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "slide_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentation_slides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kind",
            sa.String(10),
            nullable=False,
            comment="image|svg|font|bg",
        ),
        sa.Column(
            "status",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending|ready|error",
        ),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("s3_key", sa.String(2000), nullable=True),
        sa.Column("mime", sa.String(100), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True, comment="SHA256"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_passets_pres", "presentation_assets", ["presentation_id"])
    op.create_index("ix_passets_tenant_kind", "presentation_assets", ["tenant_id", "kind"])
    op.create_index(
        "ix_passets_tenant_checksum",
        "presentation_assets",
        ["tenant_id", "checksum"],
        postgresql_where=sa.text("checksum IS NOT NULL"),
    )

    # ── presentation_exports ──
    op.create_table(
        "presentation_exports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "format",
            sa.String(10),
            nullable=False,
            comment="pptx|pdf",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending|processing|done|error",
        ),
        sa.Column("s3_key", sa.String(2000), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Snapshot
        sa.Column("presentation_version", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False, comment="SHA256 of resolved slides"),
        sa.Column("slide_count", sa.Integer(), nullable=False),
        sa.Column("theme_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_pexports_tenant_id", "presentation_exports", ["tenant_id"])
    op.create_index("ix_pexports_pres_id", "presentation_exports", ["presentation_id"])

    # ── presentation_generation_runs ──
    op.create_table(
        "presentation_generation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "slide_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentation_slides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "purpose",
            sa.String(20),
            nullable=False,
            comment="outline|slide_gen|repair|regenerate|image_prompt|export_copy",
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(), nullable=True),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default=sa.text("0")),
        sa.Column("tokens_out", sa.Integer(), server_default=sa.text("0")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending|running|success|error|repaired",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("repair_attempts", sa.Integer(), server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_genruns_pres", "presentation_generation_runs", ["presentation_id"])
    op.create_index("ix_genruns_tenant_created", "presentation_generation_runs", ["tenant_id", "created_at"])
    op.create_index(
        "ix_genruns_slide",
        "presentation_generation_runs",
        ["slide_id"],
        postgresql_where=sa.text("slide_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_genruns_slide", table_name="presentation_generation_runs")
    op.drop_index("ix_genruns_tenant_created", table_name="presentation_generation_runs")
    op.drop_index("ix_genruns_pres", table_name="presentation_generation_runs")
    op.drop_table("presentation_generation_runs")

    op.drop_index("ix_pexports_pres_id", table_name="presentation_exports")
    op.drop_index("ix_pexports_tenant_id", table_name="presentation_exports")
    op.drop_table("presentation_exports")

    op.drop_index("ix_passets_tenant_checksum", table_name="presentation_assets")
    op.drop_index("ix_passets_tenant_kind", table_name="presentation_assets")
    op.drop_index("ix_passets_pres", table_name="presentation_assets")
    op.drop_table("presentation_assets")

    op.drop_index("ix_pslides_pres_pos", table_name="presentation_slides")
    op.drop_table("presentation_slides")

    op.drop_index("ix_presentations_tenant_updated", table_name="presentations")
    op.drop_index("ix_presentations_status", table_name="presentations")
    op.drop_index("ix_presentations_tenant_id", table_name="presentations")
    op.drop_table("presentations")

    op.drop_index("ix_presentation_themes_tenant_id", table_name="presentation_themes")
    op.drop_table("presentation_themes")
