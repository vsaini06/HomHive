from alembic import op
import sqlalchemy as sa

revision = "0006_research_cache"
down_revision = "0005_unknown_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_cache",
        sa.Column("household_id", sa.String(length=128), primary_key=True),
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("purpose", sa.String(length=48), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_research_cache_household_expires",
        "research_cache",
        ["household_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_cache_household_expires", table_name="research_cache")
    op.drop_table("research_cache")
