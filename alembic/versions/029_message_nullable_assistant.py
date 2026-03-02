"""Make messages.assistant_id and conversation_id nullable.

Personal dossier messages have no assistant — they use
conversation_ref_id (FK to conversations) instead.

Revision ID: 029
Revises: 028
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make assistant_id nullable (personal messages have no assistant)
    op.alter_column(
        "messages",
        "assistant_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    # Make conversation_id nullable (personal messages use conversation_ref_id)
    op.alter_column(
        "messages",
        "conversation_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Restore NOT NULL (only safe if no NULL rows exist)
    op.alter_column(
        "messages",
        "conversation_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.alter_column(
        "messages",
        "assistant_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
