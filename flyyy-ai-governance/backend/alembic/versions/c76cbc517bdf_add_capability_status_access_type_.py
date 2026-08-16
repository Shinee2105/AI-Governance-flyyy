"""add capability_status, access_type, external_event_id, indexes

Revision ID: c76cbc517bdf
Revises: b33914ffc4e3
Create Date: 2026-08-16 15:49:30.466499
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c76cbc517bdf'
down_revision: Union[str, None] = 'b33914ffc4e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ai_asset_access', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'access_type',
            sa.Enum('DIRECT_LICENSE', 'GROUP_LICENSE', 'UNKNOWN', 'NOT_OBSERVABLE', name='accesstype'),
            nullable=False, server_default='UNKNOWN'))
        batch_op.create_index('ix_ai_asset_access_asset', ['asset_id'], unique=False)

    with op.batch_alter_table('ai_assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'capability_status',
            sa.Enum('LICENSED', 'ENABLED', 'DISABLED', 'UNKNOWN', 'NOT_OBSERVABLE', name='capabilitystatus'),
            nullable=False, server_default='UNKNOWN'))
        batch_op.create_index('ix_ai_assets_connection', ['connection_id'], unique=False)

    with op.batch_alter_table('ai_interactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_event_id', sa.String(length=255), nullable=True))
        batch_op.create_index('ix_ai_interactions_asset', ['asset_id'], unique=False)
        batch_op.create_index('ix_ai_interactions_connection', ['connection_id'], unique=False)
        batch_op.create_index('ix_ai_interactions_ext_event', ['connection_id', 'external_event_id'], unique=True)
        batch_op.create_index('ix_ai_interactions_timestamp', ['timestamp'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ai_interactions', schema=None) as batch_op:
        batch_op.drop_index('ix_ai_interactions_timestamp')
        batch_op.drop_index('ix_ai_interactions_ext_event')
        batch_op.drop_index('ix_ai_interactions_connection')
        batch_op.drop_index('ix_ai_interactions_asset')
        batch_op.drop_column('external_event_id')

    with op.batch_alter_table('ai_assets', schema=None) as batch_op:
        batch_op.drop_index('ix_ai_assets_connection')
        batch_op.drop_column('capability_status')

    with op.batch_alter_table('ai_asset_access', schema=None) as batch_op:
        batch_op.drop_index('ix_ai_asset_access_asset')
        batch_op.drop_column('access_type')
