"""add deleted_at column to models for soft delete

Revision ID: e50dc541277e
Revises: 0001
Create Date: 2025-12-24 10:49:41.781466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e50dc541277e'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at column to models table for soft delete functionality."""
    op.add_column('models', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_models_deleted_at'), 'models', ['deleted_at'], unique=False)


def downgrade() -> None:
    """Remove deleted_at column from models table."""
    op.drop_index(op.f('ix_models_deleted_at'), table_name='models')
    op.drop_column('models', 'deleted_at')
               server_default=sa.text('false'),
               existing_nullable=False)
    op.drop_column('models', 'deleted_at')
    op.create_table('model_snapshots',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('model_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('payload', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('reason', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['model_id'], ['models.id'], name=op.f('model_snapshots_model_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('model_snapshots_pkey'))
    )
    op.create_index(op.f('ix_model_snapshots_model_id'), 'model_snapshots', ['model_id'], unique=False)
    op.create_table('schedule_run_snapshots',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('schedule_run_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('payload', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('created_by', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('reason', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['schedule_run_id'], ['schedule_runs.id'], name=op.f('schedule_run_snapshots_schedule_run_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('schedule_run_snapshots_pkey'))
    )
    op.create_index(op.f('ix_schedule_run_snapshots_schedule_run_id'), 'schedule_run_snapshots', ['schedule_run_id'], unique=False)
    # ### end Alembic commands ###
