"""Web search cache table.

Revision ID: 019
Revises: 018
Create Date: 2026-02-21

PR6: web_cache table for caching web search results with TTL.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False, comment="SHA-256 of normalized query"),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, comment="brave | serper | tavily"),
        sa.Column("results_json", postgresql.JSONB(), nullable=False, comment="Raw search results"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique index on query_hash + provider for cache lookup
    op.create_index(
        "ix_web_cache_lookup",
        "web_cache",
        ["query_hash", "provider"],
        unique=True,
    )
    # Index for TTL cleanup worker
    op.create_index(
        "ix_web_cache_expires_at",
        "web_cache",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_web_cache_expires_at", table_name="web_cache")
    op.drop_index("ix_web_cache_lookup", table_name="web_cache")
    op.drop_table("web_cache")
