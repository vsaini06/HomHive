"""Persist independently corroborated room categories.

Revision ID: 0012_autonomous_room_category
Revises: 0011_autonomous_jobs
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_autonomous_room_category"
down_revision = "0011_autonomous_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("autonomous_rooms", sa.Column("room_category", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("autonomous_rooms", "room_category")
