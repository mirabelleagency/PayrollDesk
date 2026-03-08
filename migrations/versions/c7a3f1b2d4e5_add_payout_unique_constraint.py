"""add_payout_unique_constraint

Revision ID: c7a3f1b2d4e5
Revises: abdd643301d5
Create Date: 2025-07-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a3f1b2d4e5"
down_revision: Union[str, None] = "abdd643301d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_payout_run_model_date",
        "payouts",
        ["schedule_run_id", "model_id", "pay_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payout_run_model_date", "payouts", type_="unique")
