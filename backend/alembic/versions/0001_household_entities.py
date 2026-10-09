"""Create household entity storage.

Revision ID: 0001_household_entities
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_household_entities"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "household_entities",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("entity_type", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("identity", sa.String(length=255), nullable=True),
        sa.Column("identification_confidence", sa.Float(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("household_entities")
