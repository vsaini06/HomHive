"""Persist household tasks.

Revision ID: 0003_tasks
Revises: 0002_observations
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_tasks"
down_revision = "0002_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("household_id", sa.String(length=128), primary_key=True),
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("task_key", sa.String(length=512), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=False),
        sa.Column("source_observation_id", sa.String(length=128), nullable=True),
        sa.Column("urgency", sa.String(length=32), nullable=False),
        sa.Column("estimated_effort_minutes", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_tasks_household_created_at", "tasks", ["household_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_household_created_at", table_name="tasks")
    op.drop_table("tasks")
