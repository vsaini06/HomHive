"""Persist source-independent evidence provenance.

Revision ID: 0007_evidence_ingestions
Revises: 0006_research_cache
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_evidence_ingestions'
down_revision = '0006_research_cache'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('evidence_ingestions',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('source_id', sa.String(128), primary_key=True),
        sa.Column('event_id', sa.String(128), primary_key=True),
        sa.Column('evidence_id', sa.String(36), nullable=False),
        sa.Column('source_type', sa.String(48), nullable=False),
        sa.Column('media_id', sa.String(36), nullable=False),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('content_sha256', sa.String(64), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True)),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('location_hint', sa.String(255)),
        sa.Column('consent_reference', sa.String(255)),
        sa.Column('processing_status', sa.String(32), nullable=False),
        sa.Column('processing_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processing_attempts', sa.Integer(), nullable=False),
    )
    op.create_table('household_notifications',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('task_id', sa.String(128), primary_key=True),
        sa.Column('state', sa.String(40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('available_after', sa.DateTime(timezone=True)),
        sa.Column('delivery_channel', sa.String(32), nullable=False),
        sa.Column('delivery_status', sa.String(40), nullable=False),
    )
    op.create_table('household_presence',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('signal_source', sa.String(40), nullable=False),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('reliability', sa.Float(), nullable=False),
        sa.Column('consent_granted', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('household_presence')
    op.drop_table('household_notifications')
    op.drop_table('evidence_ingestions')
