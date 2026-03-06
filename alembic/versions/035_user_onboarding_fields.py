"""Add onboarding profile fields to users table.

Revision ID: 035
Revises: 034
Create Date: 2026-03-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("company_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("role", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "role")
    op.drop_column("users", "company_name")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
