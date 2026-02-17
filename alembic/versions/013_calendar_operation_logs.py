"""Add calendar_operation_logs table

Revision ID: add_calendar_operation_logs
Revises: add_calendar_event_links
Create Date: 2026-02-16 14:32:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'calendar_operation_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('assistant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('op_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('request_payload', JSONB, nullable=True),
        sa.Column('response_payload', JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_calendar_operation_logs_tenant_user', 'calendar_operation_logs',
                    ['tenant_id', 'user_id'])
    op.create_index('ix_calendar_operation_logs_created_at', 'calendar_operation_logs', ['created_at'])
    op.create_foreign_key('fk_calendar_operation_logs_tenant', 'calendar_operation_logs', 'tenants',
                          ['tenant_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_table('calendar_operation_logs')
