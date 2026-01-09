"""add_payout_compensation_alerts_table

Revision ID: fe8ae1eb2e95
Revises: f61db652388a
Create Date: 2026-01-10 01:18:18.702352

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe8ae1eb2e95'
down_revision: Union[str, Sequence[str], None] = 'f61db652388a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add payout_compensation_alerts table for tracking mid-cycle compensation changes."""
    op.create_table(
        'payout_compensation_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('payout_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('schedule_run_id', sa.Integer(), nullable=False),
        sa.Column('original_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('new_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('prorated_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('alert_type', sa.String(length=30), nullable=False, server_default='compensation_changed'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['payout_id'], ['payouts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schedule_run_id'], ['schedule_runs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('payout_id', 'effective_date', name='uq_payout_alert_date'),
        sa.CheckConstraint(
            "alert_type IN ('compensation_changed', 'new_adjustment')",
            name='ck_alert_type_valid'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'acknowledged', 'applied', 'dismissed')",
            name='ck_alert_status_valid'
        ),
    )
    # Create indexes for efficient querying
    op.create_index('ix_payout_compensation_alerts_payout_id', 'payout_compensation_alerts', ['payout_id'])
    op.create_index('ix_payout_compensation_alerts_model_id', 'payout_compensation_alerts', ['model_id'])
    op.create_index('ix_payout_compensation_alerts_schedule_run_id', 'payout_compensation_alerts', ['schedule_run_id'])
    op.create_index('ix_payout_compensation_alerts_status', 'payout_compensation_alerts', ['status'])


def downgrade() -> None:
    """Remove payout_compensation_alerts table."""
    op.drop_index('ix_payout_compensation_alerts_status', table_name='payout_compensation_alerts')
    op.drop_index('ix_payout_compensation_alerts_schedule_run_id', table_name='payout_compensation_alerts')
    op.drop_index('ix_payout_compensation_alerts_model_id', table_name='payout_compensation_alerts')
    op.drop_index('ix_payout_compensation_alerts_payout_id', table_name='payout_compensation_alerts')
    op.drop_table('payout_compensation_alerts')
