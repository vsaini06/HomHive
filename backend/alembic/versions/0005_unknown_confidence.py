from alembic import op
import sqlalchemy as sa

revision = "0005_unknown_confidence"
down_revision = "0004_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("observations") as batch_op:
        batch_op.alter_column("confidence", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    connection = op.get_bind()
    unknown_count = connection.execute(sa.text("SELECT count(*) FROM observations WHERE confidence IS NULL")).scalar_one()
    if unknown_count:
        raise ValueError("Cannot downgrade while observations with unknown confidence exist")
    with op.batch_alter_table("observations") as batch_op:
        batch_op.alter_column("confidence", existing_type=sa.Float(), nullable=False)
