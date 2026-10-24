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
    # SQLite needs a table rebuild for column-nullability changes.
    # Batch mode preserves PostgreSQL's native ALTER TABLE behavior.
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "confidence", existing_type=sa.Float(), nullable=True
        )


def downgrade():
    # Preserve the migration's existing downgrade behavior.
    op.execute("UPDATE tasks SET confidence = 0 WHERE confidence IS NULL")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "confidence", existing_type=sa.Float(), nullable=False
        )
