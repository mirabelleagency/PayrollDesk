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
