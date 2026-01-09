"""Initial baseline - stamp existing production schema.

This migration represents the baseline schema that already exists in production.
Running this migration does NOT make any changes to the database - it simply
establishes a starting point for future migrations.

Revision ID: 0001
Revises: 
Create Date: 2024-12-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op upgrade - baseline represents existing schema.
    
    This baseline migration documents the schema as of v2.27.1:
    
    Tables:
    - users: Authentication and user management
    - models: Payment recipients (contractors/employees)
    - schedule_runs: Monthly payroll cycles
    - payouts: Individual payments within a cycle
    - validation_issues: Data validation problems
    - login_attempts: Security audit trail
    - audit_logs: Change tracking
    - model_compensation_adjustments: Salary changes over time
    - model_referral_terms: Commission terms per referral
    - adhoc_payments: One-time payments outside regular payroll
    - model_advances: Cash advances to models
    - advance_repayments: Repayment tracking for advances
    - payout_advance_allocations: Links payouts to advance repayments
    - commission_payouts: Commission payments for referrals
    
    If running on a fresh database, the schema will be created by
    SQLAlchemy's Base.metadata.create_all() in init_db().
    """
    pass


def downgrade() -> None:
    """No-op downgrade - cannot reverse baseline."""
    pass
