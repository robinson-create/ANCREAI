"""Extend nango_connections for calendar feature

Revision ID: 011
Revises: 010
Create Date: 2026-02-16 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajouter colonnes manquantes à nango_connections pour le calendrier

    # Ajouter user_id si n'existe pas
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('nango_connections')]

    if 'user_id' not in columns:
        op.add_column('nango_connections', sa.Column('user_id', sa.String(255), nullable=True))
        # Créer index
        op.create_index('ix_nango_connections_user_id', 'nango_connections', ['user_id'])

    if 'is_active' not in columns:
        op.add_column('nango_connections', sa.Column('is_active', sa.Boolean, server_default='true', nullable=False))

    if 'connection_metadata' not in columns:
        # Renommer metadata_json en connection_metadata et changer type
        if 'metadata_json' in columns:
            op.alter_column('nango_connections', 'metadata_json',
                          new_column_name='connection_metadata',
                          type_=sa.dialects.postgresql.JSONB,
                          postgresql_using='metadata_json::jsonb')
        else:
            op.add_column('nango_connections',
                         sa.Column('connection_metadata', sa.dialects.postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_index('ix_nango_connections_user_id', 'nango_connections')
    op.drop_column('nango_connections', 'user_id')
    op.drop_column('nango_connections', 'is_active')

    # Renommer connection_metadata en metadata_json
    op.alter_column('nango_connections', 'connection_metadata',
                   new_column_name='metadata_json',
                   type_=sa.Text)
