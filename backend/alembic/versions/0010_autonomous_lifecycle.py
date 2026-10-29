"""Durable autonomous tasks with reviewed evidence history.

Revision ID: 0010_autonomous_lifecycle
Revises: 0009_nullable_task_confidence
"""
from alembic import op
import sqlalchemy as sa
revision = "0010_autonomous_lifecycle"
down_revision = "0009_nullable_task_confidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("autonomous_tasks",
        sa.Column("household_id", sa.String(128), primary_key=True),
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("physical_room_id", sa.String(128), nullable=False),
        sa.Column("action_key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("action", sa.String(2000), nullable=False),
        sa.Column("criteria", sa.String(1000), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("effort_min", sa.Integer(), nullable=True),
        sa.Column("effort_max", sa.Integer(), nullable=True),
        sa.Column("task_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("household_id", "physical_room_id", "action_key", name="uq_autonomous_task_per_room"))
    op.create_index("ix_autonomous_tasks_room", "autonomous_tasks", ["household_id", "physical_room_id"])
    op.create_table("autonomous_task_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("household_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=False),
        sa.Column("media_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id", "task_id"], ["autonomous_tasks.household_id", "autonomous_tasks.id"]),
        sa.UniqueConstraint("household_id", "task_id", "media_id", "kind", name="uq_autonomous_event_once"))
    op.create_index("ix_autonomous_event_task", "autonomous_task_events", ["household_id", "task_id", "created_at"])


def downgrade():

    op.drop_index("ix_autonomous_event_task", table_name="autonomous_task_events")
    op.drop_table("autonomous_task_events")
    op.drop_index("ix_autonomous_tasks_room", table_name="autonomous_tasks")
    op.drop_table("autonomous_tasks")
