"""Referral commission dashboard endpoints."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, DefaultDict, Iterable

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import User
from app.commission import ReferralScheduleEntry, generate_referral_schedule
from app.database import get_session
from app.dependencies import templates
from app.routers.auth import get_current_user

router = APIRouter(prefix="/commissions", tags=["Commissions"])

_HORIZON_MONTHS = 4
_DECIMAL_ZERO = Decimal("0")


@router.get("/")
def commissions_dashboard(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    entries = generate_referral_schedule(db, months_forward=_HORIZON_MONTHS)
    stats = _build_stats(entries)
    grouped_schedule = _group_entries_by_date(entries)

    context = {
        "request": request,
        "user": user,
        "stats": stats,
        "entries": entries,
        "grouped_schedule": grouped_schedule,
        "horizon_months": _HORIZON_MONTHS,
    }
    return templates.TemplateResponse("commissions/index.html", context)


def _build_stats(entries: Iterable[ReferralScheduleEntry]) -> dict[str, Any]:
    unique_referrers = set()
    unique_referrals = set()
    total_amount = _DECIMAL_ZERO
    monthly_slots = 0
    mid_month_slots = 0
    frequency_counts: dict[str, int] = defaultdict(int)
    sorted_entries = list(entries)

    for entry in sorted_entries:
        unique_referrers.add(entry.referrer_id)
        unique_referrals.add(entry.referral_id)
        total_amount += entry.amount
        if entry.schedule_type == "monthly":
            monthly_slots += 1
        elif entry.schedule_type == "mid-month":
            mid_month_slots += 1
        normalized_freq = (entry.referrer_frequency or "dual").strip().lower()
        frequency_counts[normalized_freq] += 1

    next_pay_date = sorted_entries[0].pay_date if sorted_entries else None

    return {
        "unique_referrers": len(unique_referrers),
        "unique_referrals": len(unique_referrals),
        "upcoming_events": len(sorted_entries),
        "projected_total": total_amount,
        "next_pay_date": next_pay_date,
        "monthly_slots": monthly_slots,
        "mid_month_slots": mid_month_slots,
        "frequency_counts": dict(frequency_counts),
    }


def _group_entries_by_date(entries: Iterable[ReferralScheduleEntry]) -> list[dict[str, Any]]:
    buckets: DefaultDict[Any, dict[str, Any]] = defaultdict(lambda: {
        "total": _DECIMAL_ZERO,
        "count": 0,
        "referrer_ids": set(),
        "items": [],
    })

    for entry in entries:
        bucket = buckets[entry.pay_date]
        bucket["total"] += entry.amount
        bucket["count"] += 1
        bucket["referrer_ids"].add(entry.referrer_id)
        bucket["items"].append(entry)

    grouped: list[dict[str, Any]] = []
    for pay_date in sorted(buckets):
        bucket = buckets[pay_date]
        grouped.append(
            {
                "date": pay_date,
                "total": bucket["total"],
                "count": bucket["count"],
                "referrer_count": len(bucket["referrer_ids"]),
                "items": bucket["items"],
            }
        )
    return grouped
