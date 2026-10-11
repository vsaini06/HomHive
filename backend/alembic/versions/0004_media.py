"""Store media metadata.

Revision ID: 0004_media
Revises: 0003_tasks
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_media'
down_revision = '0003_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'media',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('media')
