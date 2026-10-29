"""Household context signals and quiet-hour preferences.

Revision ID: 0015_household_coordination
Revises: 0014_autonomous_automation
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_household_coordination'
down_revision = '0014_autonomous_automation'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('household_context_signals',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('kind', sa.String(40), primary_key=True),
        sa.Column('state', sa.String(40), nullable=False),
        sa.Column('source', sa.String(40), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consent', sa.Boolean, nullable=False))
    op.create_table('household_quiet_hours',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('enabled', sa.Boolean, nullable=False),
        sa.Column('start_time', sa.String(5), nullable=False),
        sa.Column('end_time', sa.String(5), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('household_quiet_hours')
    op.drop_table('household_context_signals')
