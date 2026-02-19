"""Add folders and folder_items tables for organizing conversations, documents, emails.

Revision ID: 016
Revises: 015
Create Date: 2026-02-17

Folders allow users to group conversations, workspace documents, and email threads
into hierarchical contexts.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "folders",
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
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
    op.create_index("ix_folders_tenant_id", "folders", ["tenant_id"])

    op.create_table(
        "folder_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_type",
            sa.String(20),
            nullable=False,
            comment="conversation | document | email_thread",
        ),
        sa.Column("item_id", sa.String(255), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("folder_id", "item_type", "item_id", name="uq_folder_items_folder_type_id"),
    )
    op.create_index("ix_folder_items_folder_id", "folder_items", ["folder_id"])
    op.create_index("ix_folder_items_item", "folder_items", ["item_type", "item_id"])


def downgrade() -> None:
    op.drop_index("ix_folder_items_item", table_name="folder_items")
    op.drop_index("ix_folder_items_folder_id", table_name="folder_items")
    op.drop_table("folder_items")
    op.drop_index("ix_folders_tenant_id", table_name="folders")
    op.drop_table("folders")
