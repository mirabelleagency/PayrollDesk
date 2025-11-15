"""Standalone commission helpers (kept separate from core payroll runs)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models import Model, ModelReferralTerm


@dataclass
class CommissionSummary:
    referrer_id: int
    total_referrals: int
    active_referrals: int
    estimated_monthly_commission: Decimal
    has_active_program: bool


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
    status: str = "unpaid"  # "unpaid" or "paid"
    commission_payout_id: int | None = None


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


def _referral_term_map(db: Session, referrer_id: int) -> dict[int, ModelReferralTerm]:
    if not referrer_id:
        return {}
    rows = (
        db.query(ModelReferralTerm)
        .filter(ModelReferralTerm.referrer_model_id == referrer_id)
        .all()
    )
    return {row.referral_model_id: row for row in rows}


def build_commission_summary(db: Session, referrer: Model) -> CommissionSummary:
    """Compute a simple commission snapshot for display on the profile page.

    For now this is a purely informational calculation – it does not
    create payouts or alter existing payroll runs.
    """

    referrals = get_eligible_referrals(db, referrer)
    term_map = _referral_term_map(db, referrer.id or 0)
    estimated = Decimal("0")
    active_referrals = 0

    for referral in referrals:
        term = term_map.get(referral.id or 0)
        if not term or not term.is_active:
            continue
        amount = Decimal(term.commission_per_referral or Decimal("0"))
        if amount <= 0:
            continue
        frequency = (term.commission_payout_frequency or "dual").strip().lower()
        windows = _frequency_windows(frequency)
        multiplier = Decimal(len(windows))
        estimated += amount * multiplier
        active_referrals += 1

    return CommissionSummary(
        referrer_id=referrer.id or 0,
        total_referrals=len(referrals),
        active_referrals=active_referrals,
        estimated_monthly_commission=estimated,
        has_active_program=active_referrals > 0,
    )


def generate_referral_schedule(
    db: Session,
    *,
    months_forward: int = 3,
    today: date | None = None,
) -> list[ReferralScheduleEntry]:
    """Build upcoming referral commission payouts for all active referrers."""
    from app.models import CommissionPayout

    today = today or date.today()
    if months_forward <= 0:
        return []

    referrers: Iterable[Model] = (
        db.query(Model)
        .filter(Model.referral_terms.any(ModelReferralTerm.is_active.is_(True)))
        .order_by(Model.code.asc())
        .all()
    )

    # Load existing commission payout records to populate status
    existing_payouts = db.query(CommissionPayout).all()
    payout_map = {
        (p.referrer_model_id, p.referral_model_id, p.pay_date, p.schedule_type): p
        for p in existing_payouts
    }

    entries: list[ReferralScheduleEntry] = []
    for referrer in referrers:
        if not referrer.id:
            continue
        referrals = get_eligible_referrals(db, referrer)
        if not referrals:
            continue
        term_map = _referral_term_map(db, referrer.id)
        for referral in referrals:
            term = term_map.get(referral.id or 0)
            if not term or not term.is_active:
                continue
            amount = Decimal(term.commission_per_referral or Decimal("0"))
            if amount <= 0:
                continue
            frequency = (term.commission_payout_frequency or "dual").strip().lower()
            windows = _frequency_windows(frequency)
            if not windows:
                continue
            entries.extend(
                _build_schedule_for_referral(
                    db,
                    referrer,
                    referral,
                    amount,
                    windows,
                    frequency,
                    payout_map=payout_map,
                    months_forward=months_forward,
                    today=today,
                )
            )

    entries.sort(key=lambda item: (item.pay_date, item.referrer_name.lower(), item.referral_name.lower()))
    return entries


def _build_schedule_for_referral(
    db: Session,
    referrer: Model,
    referral: Model,
    per_referral: Decimal,
    windows: Iterable[str],
    frequency_label: str,
    *,
    payout_map: dict,
    months_forward: int,
    today: date,
) -> list[ReferralScheduleEntry]:
    from app.models import CommissionPayout

    schedule: list[ReferralScheduleEntry] = []
    referrer_name = _display_name(referrer)
    allowed = tuple(windows)

    accepted_on = referral.start_date
    referral_name = _display_name(referral)
    for pay_date, schedule_type in _iter_payment_dates(accepted_on, today, months_forward, allowed):
        # Check if a payout record exists for this entry
        payout_key = (referrer.id, referral.id, pay_date, schedule_type)
        existing_payout = payout_map.get(payout_key)
        
        if existing_payout:
            status = existing_payout.status
            payout_id = existing_payout.id
        else:
            # Auto-create payout record for tracking
            new_payout = CommissionPayout(
                referrer_model_id=referrer.id or 0,
                referral_model_id=referral.id or 0,
                pay_date=pay_date,
                schedule_type=schedule_type,
                amount=per_referral,
                status="unpaid",
            )
            db.add(new_payout)
            db.flush()
            status = "unpaid"
            payout_id = new_payout.id
            payout_map[payout_key] = new_payout

        schedule.append(
            ReferralScheduleEntry(
                referrer_id=referrer.id or 0,
                referrer_name=referrer_name,
                referrer_frequency=frequency_label,
                referral_id=referral.id or 0,
                referral_name=referral_name,
                accepted_on=accepted_on,
                pay_date=pay_date,
                schedule_type=schedule_type,
                amount=per_referral,
                status=status,
                commission_payout_id=payout_id,
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
