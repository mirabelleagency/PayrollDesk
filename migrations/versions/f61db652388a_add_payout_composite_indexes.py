"""add payout composite indexes

Revision ID: f61db652388a
Revises: e50dc541277e
Create Date: 2025-12-24 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f61db652388a'
down_revision: Union[str, Sequence[str], None] = 'e50dc541277e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes to payouts table for query optimization."""
    # Index for filtering by run + status (common dashboard queries)
    op.create_index('idx_payout_run_status', 'payouts', ['schedule_run_id', 'status'], unique=False)
    # Index for filtering by run + model (common join queries)
    op.create_index('idx_payout_run_model', 'payouts', ['schedule_run_id', 'model_id'], unique=False)
    # Single-column index on schedule_run_id for FK lookups
    op.create_index(op.f('ix_payouts_schedule_run_id'), 'payouts', ['schedule_run_id'], unique=False)
    # Single-column index on model_id for FK lookups
    op.create_index(op.f('ix_payouts_model_id'), 'payouts', ['model_id'], unique=False)


def downgrade() -> None:
    """Remove payout indexes."""
    op.drop_index(op.f('ix_payouts_model_id'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_schedule_run_id'), table_name='payouts')
    op.drop_index('idx_payout_run_model', table_name='payouts')
    op.drop_index('idx_payout_run_status', table_name='payouts')
