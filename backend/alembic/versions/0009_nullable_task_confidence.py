"""Allow verified tasks without an invented numeric confidence.

Revision ID: 0009_nullable_task_confidence
Revises: 0008_accounts
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_nullable_task_confidence"
down_revision = "0008_accounts"
branch_labels = None
depends_on = None


def upgrade():


    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "confidence", existing_type=sa.Float(), nullable=True
        )


def downgrade():

    op.execute("UPDATE tasks SET confidence = 0 WHERE confidence IS NULL")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "confidence", existing_type=sa.Float(), nullable=False
        )
