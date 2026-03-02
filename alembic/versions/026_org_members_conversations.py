"""Add org_members, dossiers, conversations, assistant_permissions tables.

Foundational migration for the org/personal scope separation:
- org_members: N:M link between users and tenants (replaces 1:1)
- dossiers: personal workspaces within an org
- conversations: first-class entity with explicit scope + CHECK constraint
- assistant_permissions: controls which members can use which assistants
- messages.conversation_ref_id: FK to conversations (nullable during transition)

Backfill: creates an org_member(role=admin, status=active) for every
existing user using their current user.tenant_id.

Revision ID: 026
Revises: 025
Create Date: 2026-03-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. content_scope enum type ---
    content_scope_enum = postgresql.ENUM("org", "personal", name="content_scope", create_type=False)
    content_scope_enum.create(op.get_bind(), checkfirst=True)

    # --- 2. org_members ---
    op.create_table(
        "org_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_org_members_tenant_user"),
    )

    # --- 3. Backfill: every existing user becomes admin of their tenant ---
    op.execute(
        """
        INSERT INTO org_members (id, tenant_id, user_id, role, status, joined_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            u.tenant_id,
            u.id,
            'admin',
            'active',
            u.created_at,
            now(),
            now()
        FROM users u
        WHERE u.tenant_id IS NOT NULL
        ON CONFLICT (tenant_id, user_id) DO NOTHING
        """
    )

    # --- 4. dossiers ---
    op.create_table(
        "dossiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- 5. conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            """
            (scope = 'org' AND assistant_id IS NOT NULL AND dossier_id IS NULL)
            OR
            (scope = 'personal' AND dossier_id IS NOT NULL AND assistant_id IS NULL)
            """,
            name="ck_conversations_scope_coherence",
        ),
    )

    # --- 6. assistant_permissions ---
    op.create_table(
        "assistant_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org_members.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("assistant_id", "member_id", name="uq_assistant_permissions_assistant_member"),
    )

    # --- 7. messages.conversation_ref_id (nullable FK, transition column) ---
    op.add_column(
        "messages",
        sa.Column(
            "conversation_ref_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_messages_conversation_ref_id", "messages", ["conversation_ref_id"])


def downgrade() -> None:
    # Reverse order
    op.drop_index("ix_messages_conversation_ref_id", table_name="messages")
    op.drop_column("messages", "conversation_ref_id")
    op.drop_table("assistant_permissions")
    op.drop_table("conversations")
    op.drop_table("dossiers")
    op.drop_table("org_members")

    # Drop enum type
    content_scope_enum = postgresql.ENUM("org", "personal", name="content_scope", create_type=False)
    content_scope_enum.drop(op.get_bind(), checkfirst=True)
