"""Add payouts.amount_overridden so a refresh keeps amounts an admin chose.

Additive: existing payouts get false, i.e. today's behaviour (recalculated on
refresh) until an amount is set by hand.

Revision ID: d9e3f4a5b6c7
Revises: c8d2e3f4a5b6
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e3f4a5b6c7"
down_revision: Union[str, None] = "c8d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payouts",
        sa.Column("amount_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("payouts", "amount_overridden")
