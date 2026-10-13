"""Repair payouts whose gross_amount no longer matches amount + advance deduction.

Editing a payout's amount (applying a compensation alert, re-importing a
sheet) used to leave gross_amount at its generated value. This recomputes it
for every payout where it is set and disagrees with
amount + planned allocations + recorded repayments. Payouts with no
gross_amount (pre-breakdown history) are left alone.

Revision ID: b7c1d2e3f4a5
Revises: d4e5f6a7b8c9
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EXPECTED_GROSS = """
    payouts.amount
    + COALESCE((SELECT SUM(a.planned_amount) FROM payout_advance_allocations a
                WHERE a.payout_id = payouts.id), 0)
    + COALESCE((SELECT SUM(r.amount) FROM advance_repayments r
                WHERE r.payout_id = payouts.id), 0)
"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE payouts
           SET gross_amount = {_EXPECTED_GROSS}
         WHERE gross_amount IS NOT NULL
           AND gross_amount <> {_EXPECTED_GROSS}
        """
    )


def downgrade() -> None:
    """Data repair only; the previous (stale) values are not kept."""
    pass
