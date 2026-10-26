"""Durable household recommendations and preferred household-work windows."""
from alembic import op
import sqlalchemy as sa

revision = "0014_autonomous_automation"
down_revision = "0013_autonomous_scan_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("autonomous_availability",
        sa.Column("household_id", sa.String(128), primary_key=True),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("end_time", sa.String(5), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("autonomous_alerts",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("household_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=False),
        sa.Column("media_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("detail", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("household_id", "task_id", "media_id", "kind", name="uq_autonomous_alert_once"))
    op.create_index("ix_autonomous_alert_household", "autonomous_alerts", ["household_id", "created_at"])


def downgrade():
    op.drop_index("ix_autonomous_alert_household", table_name="autonomous_alerts")
    op.drop_table("autonomous_alerts")
    op.drop_table("autonomous_availability")
