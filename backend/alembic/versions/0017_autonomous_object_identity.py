"""Introduce persistent objects and object-scoped autonomous tasks.

Revision ID: 0017_autonomous_object_identity
Revises: 0016_quiet_hours_timezone
"""
from alembic import op
import sqlalchemy as sa
revision = '0017_autonomous_object_identity'
down_revision = '0016_quiet_hours_timezone'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('autonomous_objects',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('room_id', sa.String(128), nullable=True),
        sa.Column('reference_media_id', sa.String(128), nullable=False),
        sa.Column('demo_family', sa.String(128), nullable=True),
        sa.Column('image_hash', sa.String(64), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('identity_hint', sa.String(120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_autonomous_objects_household', 'autonomous_objects', ['household_id', 'kind'])
    op.create_table('autonomous_object_views',
        sa.Column('household_id', sa.String(128), primary_key=True),
        sa.Column('media_id', sa.String(128), primary_key=True),
        sa.Column('object_id', sa.String(128), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['household_id', 'object_id'],
            ['autonomous_objects.household_id', 'autonomous_objects.id']))

    with op.batch_alter_table('autonomous_tasks') as batch:
        batch.alter_column('physical_room_id', existing_type=sa.String(128), nullable=True)
        batch.add_column(sa.Column('object_id', sa.String(128), nullable=True))
        batch.create_unique_constraint('uq_autonomous_task_per_object', ['household_id', 'object_id', 'action_key'])


def downgrade():

    bind = op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM autonomous_tasks WHERE object_id IS NOT NULL')).scalar():
        raise RuntimeError('Cannot downgrade with object-linked tasks; archive and migrate them first')
    with op.batch_alter_table('autonomous_tasks') as batch:
        batch.drop_constraint('uq_autonomous_task_per_object', type_='unique')
        batch.drop_column('object_id')
        batch.alter_column('physical_room_id', existing_type=sa.String(128), nullable=False)
    op.drop_table('autonomous_object_views')
    op.drop_index('ix_autonomous_objects_household', table_name='autonomous_objects')
    op.drop_table('autonomous_objects')
