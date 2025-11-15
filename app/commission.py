"""Standalone commission helpers (kept separate from core payroll runs)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from app.models import Model


@dataclass
class CommissionSummary:
    referrer_id: int
    commission_active: bool
    commission_per_referral: Decimal
    total_referrals: int
    estimated_monthly_commission: Decimal


def get_eligible_referrals(db: Session, referrer: Model) -> List[Model]:
    """Return active referred models for a given referrer.

    This does **not** modify any payroll or payout data; it only
    inspects `Model` rows, so it is safe to call from views.
    """

    if referrer.id is None:
        return []

    return (
        db.query(Model)
        .filter(
            Model.referred_by_model_id == referrer.id,
            Model.status == "Active",
        )
        .order_by(Model.start_date.asc())
        .all()
    )


def build_commission_summary(db: Session, referrer: Model) -> CommissionSummary:
    """Compute a simple commission snapshot for display on the profile page.

    For now this is a purely informational calculation – it does not
    create payouts or alter existing payroll runs.
    """

    per_referral = referrer.commission_per_referral or Decimal("0")
    referrals = get_eligible_referrals(db, referrer)
    total_referrals = len(referrals)
    estimated = per_referral * Decimal(str(total_referrals))

    return CommissionSummary(
        referrer_id=referrer.id or 0,
        commission_active=bool(referrer.commission_active),
        commission_per_referral=per_referral,
        total_referrals=total_referrals,
        estimated_monthly_commission=estimated,
    )
