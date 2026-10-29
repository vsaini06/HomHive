"""Persist the household time zone for quiet-hour calculations.

Revision ID: 0016_quiet_hours_timezone
Revises: 0015_household_coordination
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_quiet_hours_timezone'
down_revision = '0015_household_coordination'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('household_quiet_hours', sa.Column('timezone', sa.String(64), nullable=False, server_default='UTC'))
    op.execute("UPDATE household_quiet_hours SET timezone = COALESCE("
               "(SELECT a.timezone FROM autonomous_availability AS a "
               "WHERE a.household_id = household_quiet_hours.household_id), 'UTC')")


def downgrade():
    op.drop_column('household_quiet_hours', 'timezone')
