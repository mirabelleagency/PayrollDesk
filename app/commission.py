"""Standalone commission helpers (kept separate from core payroll runs)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models import Model


@dataclass
class CommissionSummary:
    referrer_id: int
    commission_active: bool
    commission_per_referral: Decimal
    total_referrals: int
    estimated_monthly_commission: Decimal
    payout_frequency: str


@dataclass
class ReferralScheduleEntry:
    """Represents a single planned commission payout."""

    referrer_id: int
    referrer_name: str
    referrer_frequency: str
    referral_id: int
    referral_name: str
    accepted_on: date
    pay_date: date
    schedule_type: str  # "monthly" or "mid-month"
    amount: Decimal


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
    frequency = (referrer.commission_payout_frequency or "dual").strip().lower()
    multiplier = Decimal(len(_frequency_windows(frequency))) or Decimal("1")
    estimated = per_referral * Decimal(str(total_referrals)) * multiplier

    return CommissionSummary(
        referrer_id=referrer.id or 0,
        commission_active=bool(referrer.commission_active),
        commission_per_referral=per_referral,
        total_referrals=total_referrals,
        estimated_monthly_commission=estimated,
        payout_frequency=frequency,
    )


def generate_referral_schedule(
    db: Session,
    *,
    months_forward: int = 3,
    today: date | None = None,
) -> list[ReferralScheduleEntry]:
    """Build upcoming referral commission payouts for all active referrers."""

    today = today or date.today()
    if months_forward <= 0:
        return []

    referrers: Iterable[Model] = (
        db.query(Model)
        .filter(Model.commission_active.is_(True))
        .order_by(Model.code.asc())
        .all()
    )

    entries: list[ReferralScheduleEntry] = []
    for referrer in referrers:
        if not referrer.id:
            continue
        per_referral = referrer.commission_per_referral or Decimal("0")
        if per_referral <= 0:
            continue
        frequency = (referrer.commission_payout_frequency or "dual").strip().lower()
        windows = _frequency_windows(frequency)
        if not windows:
            continue
        referrals = get_eligible_referrals(db, referrer)
        if not referrals:
            continue
        entries.extend(
            _build_schedule_for_referrals(
                referrer,
                referrals,
                per_referral,
                windows,
                months_forward=months_forward,
                today=today,
            )
        )

    entries.sort(key=lambda item: (item.pay_date, item.referrer_name.lower(), item.referral_name.lower()))
    return entries


def _build_schedule_for_referrals(
    referrer: Model,
    referrals: Iterable[Model],
    per_referral: Decimal,
    windows: Iterable[str],
    *,
    months_forward: int,
    today: date,
) -> list[ReferralScheduleEntry]:
    schedule: list[ReferralScheduleEntry] = []
    referrer_name = _display_name(referrer)
    allowed = tuple(windows)

    for referral in referrals:
        accepted_on = referral.start_date
        referral_name = _display_name(referral)
        for pay_date, schedule_type in _iter_payment_dates(accepted_on, today, months_forward, allowed):
            schedule.append(
                ReferralScheduleEntry(
                    referrer_id=referrer.id or 0,
                    referrer_name=referrer_name,
                    referrer_frequency=(referrer.commission_payout_frequency or "dual"),
                    referral_id=referral.id or 0,
                    referral_name=referral_name,
                    accepted_on=accepted_on,
                    pay_date=pay_date,
                    schedule_type=schedule_type,
                    amount=per_referral,
                )
            )

    return schedule


def _iter_payment_dates(
    accepted_on: date,
    today: date,
    months_forward: int,
    allowed_windows: Iterable[str],
) -> Iterable[tuple[date, str]]:
    """Yield semi-monthly payment dates (1st & 14th) after acceptance."""

    if not accepted_on:
        return

    anchor_source = accepted_on if accepted_on > today else today
    anchor_month_start = anchor_source.replace(day=1)

    allowed = {window.strip().lower() for window in allowed_windows if window}
    if not allowed:
        return

    for month_offset in range(months_forward):
        month_start = _add_months(anchor_month_start, month_offset)
        first_day = month_start
        if "monthly" in allowed and first_day >= accepted_on and first_day >= today:
            yield first_day, "monthly"

        mid_month = month_start.replace(day=14)
        if "mid-month" in allowed and mid_month >= accepted_on and mid_month >= today:
            yield mid_month, "mid-month"


def _frequency_windows(frequency: str) -> tuple[str, ...]:
    mapping = {
        "monthly": ("monthly",),
        "mid_month": ("mid-month",),
        "dual": ("monthly", "mid-month"),
    }
    normalized = (frequency or "dual").strip().lower()
    return mapping.get(normalized, mapping["dual"])


def _add_months(source: date, offset: int) -> date:
    month_index = source.month - 1 + offset
    year = source.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _display_name(model: Model) -> str:
    if model.working_name:
        return model.working_name
    if model.real_name:
        return model.real_name
    if model.code:
        return model.code
    if model.id:
        return f"Model #{model.id}"
    return "Model"
