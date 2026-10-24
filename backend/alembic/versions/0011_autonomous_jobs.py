"""Durable autonomous scan queue and explicit physical-room registry.

Revision ID: 0011_autonomous_jobs
Revises: 0010_autonomous_lifecycle
"""
from alembic import op
import sqlalchemy as sa
revision='0011_autonomous_jobs'
down_revision='0010_autonomous_lifecycle'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('autonomous_rooms',
        sa.Column('household_id',sa.String(128),primary_key=True),
        sa.Column('room_id',sa.String(128),primary_key=True),
        sa.Column('reference_media_id',sa.String(128),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('household_id','reference_media_id',name='uq_autonomous_room_reference'))
    op.create_table('autonomous_scan_jobs',
        sa.Column('id',sa.String(128),primary_key=True),
        sa.Column('household_id',sa.String(128),nullable=False),
        sa.Column('media_id',sa.String(128),nullable=False),
        sa.Column('room_id',sa.String(128),nullable=True),
        sa.Column('state',sa.String(32),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('next_attempt_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('message',sa.String(160),nullable=False),
        sa.UniqueConstraint('household_id','media_id',name='uq_autonomous_job_media'))
    op.create_index('ix_autonomous_job_pending','autonomous_scan_jobs',['state','next_attempt_at'])

def downgrade():
    op.drop_index('ix_autonomous_job_pending',table_name='autonomous_scan_jobs')
    op.drop_table('autonomous_scan_jobs')
    op.drop_table('autonomous_rooms')
