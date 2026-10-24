"""Add user accounts, household memberships, and revocable sessions.

Revision ID: 0008_accounts
Revises: 0007_evidence_ingestions
"""
from alembic import op
import sqlalchemy as sa
revision = "0008_accounts"
down_revision = "0007_evidence_ingestions"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False))
    op.create_table("household_memberships",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("household_id", sa.String(128), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False))
    op.create_table("user_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("user_sessions")
    op.drop_table("household_memberships")
    op.drop_table("users")
