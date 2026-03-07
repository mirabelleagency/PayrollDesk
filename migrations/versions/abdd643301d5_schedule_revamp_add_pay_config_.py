"""schedule_revamp_add_pay_config_frequency_plan_amendment_payout_locking

Revision ID: abdd643301d5
Revises: fe8ae1eb2e95
Create Date: 2026-03-08 02:44:11.286746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


# revision identifiers, used by Alembic.
revision: str = 'abdd643301d5'
down_revision: Union[str, Sequence[str], None] = 'fe8ae1eb2e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new tables (skip if already created by create_all)
    if not _table_exists('pay_configs'):
        op.create_table('pay_configs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('pay_days', sa.Text(), nullable=False, server_default='[7, 14, 21, "eom"]'),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
            sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )
    if not _table_exists('frequency_plans'):
        op.create_table('frequency_plans',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('pay_day_indices', sa.Text(), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )
    if not _table_exists('schedule_amendments'):
        op.create_table('schedule_amendments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('schedule_run_id', sa.Integer(), nullable=False),
            sa.Column('amendment_type', sa.String(length=30), nullable=False),
            sa.Column('models_affected', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('changes_summary', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_by', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['schedule_run_id'], ['schedule_runs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_schedule_amendments_schedule_run_id'), 'schedule_amendments', ['schedule_run_id'], unique=False)

    # Seed default data if tables are empty
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM pay_configs")).scalar()
    if count == 0:
        op.execute(
            "INSERT INTO pay_configs (name, pay_days, currency, is_default, created_at, updated_at) "
            "VALUES ('Default', '[7, 14, 21, \"eom\"]', 'USD', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    count = bind.execute(sa.text("SELECT COUNT(*) FROM frequency_plans")).scalar()
    if count == 0:
        op.execute(
            "INSERT INTO frequency_plans (name, pay_day_indices, display_name, is_active, created_at) VALUES "
            "('weekly', '[0, 1, 2, 3]', 'Weekly (4x/month)', 1, CURRENT_TIMESTAMP)"
        )
        op.execute(
            "INSERT INTO frequency_plans (name, pay_day_indices, display_name, is_active, created_at) VALUES "
            "('biweekly', '[1, 3]', 'Biweekly (2x/month)', 1, CURRENT_TIMESTAMP)"
        )
        op.execute(
            "INSERT INTO frequency_plans (name, pay_day_indices, display_name, is_active, created_at) VALUES "
            "('monthly', '[3]', 'Monthly (1x/month)', 1, CURRENT_TIMESTAMP)"
        )

    # Add columns to existing tables (skip if already present)
    if not _column_exists('payouts', 'is_locked'):
        op.add_column('payouts', sa.Column('is_locked', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    if not _column_exists('payouts', 'gross_amount'):
        op.add_column('payouts', sa.Column('gross_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    if not _column_exists('schedule_runs', 'run_status'):
        op.add_column('schedule_runs', sa.Column('run_status', sa.String(length=20), nullable=False, server_default='ready'))
    if not _column_exists('schedule_runs', 'error_message'):
        op.add_column('schedule_runs', sa.Column('error_message', sa.Text(), nullable=True))
    if not _column_exists('schedule_runs', 'pay_config_id'):
        op.add_column('schedule_runs', sa.Column('pay_config_id', sa.Integer(), nullable=True))
        # FK constraint handled by create_all for SQLite; for PostgreSQL use batch mode or direct ALTER
        try:
            op.create_foreign_key('fk_schedule_runs_pay_config', 'schedule_runs', 'pay_configs', ['pay_config_id'], ['id'], ondelete='SET NULL')
        except NotImplementedError:
            pass  # SQLite: FK already defined via create_all


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_schedule_runs_pay_config', 'schedule_runs', type_='foreignkey')
    op.drop_column('schedule_runs', 'pay_config_id')
    op.drop_column('schedule_runs', 'error_message')
    op.drop_column('schedule_runs', 'run_status')
    op.drop_column('payouts', 'gross_amount')
    op.drop_column('payouts', 'is_locked')
    op.drop_index(op.f('ix_schedule_amendments_schedule_run_id'), table_name='schedule_amendments')
    op.drop_table('schedule_amendments')
    op.drop_table('frequency_plans')
    op.drop_table('pay_configs')
