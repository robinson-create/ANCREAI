"""Add calendar_event_links table

Revision ID: add_calendar_event_links
Revises: add_nango_connections
Create Date: 2026-02-16 14:31:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'calendar_event_links',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('assistant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('external_event_id', sa.String(500), nullable=False),
        sa.Column('external_calendar_id', sa.String(500), nullable=False, server_default='primary'),
        sa.Column('title_snapshot', sa.String(500), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(100), nullable=False, server_default='Europe/Paris'),
        sa.Column('attendees_hash', sa.String(64), nullable=True),
        sa.Column('has_video_conference', sa.Boolean, default=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_index('ix_calendar_event_links_tenant_user', 'calendar_event_links', ['tenant_id', 'user_id'])
    op.create_index('ix_calendar_event_links_starts_at', 'calendar_event_links', ['starts_at'])
    op.create_unique_constraint('uq_calendar_event_links_external', 'calendar_event_links',
                                ['tenant_id', 'user_id', 'provider', 'external_event_id'])
    op.create_foreign_key('fk_calendar_event_links_tenant', 'calendar_event_links', 'tenants',
                          ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_calendar_event_links_assistant', 'calendar_event_links', 'assistants',
                          ['assistant_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_table('calendar_event_links')
