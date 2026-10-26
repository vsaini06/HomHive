"""Record per-scan review summaries and user-corrected room categories.

Revision ID: 0013_autonomous_scan_review
Revises: 0012_autonomous_room_category
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_autonomous_scan_review"
down_revision = "0012_autonomous_room_category"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("autonomous_scan_jobs", sa.Column("review_summary", sa.JSON(), nullable=True))
    op.add_column("autonomous_rooms", sa.Column(
        "room_category_source", sa.String(32), nullable=False,
        server_default="ai_reviewed"))


def downgrade():
    op.drop_column("autonomous_rooms", "room_category_source")
    op.drop_column("autonomous_scan_jobs", "review_summary")
