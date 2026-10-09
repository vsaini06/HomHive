"""Persist household observations.

Revision ID: 0002_observations
Revises: 0001_household_entities
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_observations"
down_revision = "0001_household_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("household_id", sa.String(length=128), primary_key=True),
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_observations_household_timestamp",
        "observations", ["household_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_household_timestamp", table_name="observations")
    op.drop_table("observations")
