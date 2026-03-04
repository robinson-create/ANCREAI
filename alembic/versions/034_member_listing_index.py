"""Add composite index on org_members for member listing queries.

Revision ID: 034
Revises: 033
Create Date: 2026-03-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_org_members_tenant_status",
        "org_members",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_members_tenant_status", table_name="org_members")
