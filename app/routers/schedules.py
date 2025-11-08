"""Routes for managing payroll cycles."""
# pyright: reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOperatorIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false
from __future__ import annotations

import calendar
import csv
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Sequence, cast, Any
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlencode

from app import crud
from app.auth import User
from app.database import get_session
from app.dependencies import templates
from app.core.formatting import format_display_date
from app.models import AdhocPayment, PAYOUT_STATUS_ENUM, Payout, Model, ScheduleRun
from app.routers.auth import get_current_user, get_admin_user
from app.services import PayrollService

router = APIRouter(prefix="/schedules", tags=["Schedules"])

DEFAULT_EXPORT_DIR = Path("exports")

QUICK_RANGE_OPTIONS = [
    {"id": "past_7_days", "label": "Past 7 Days", "days": 7},
    {"id": "past_30_days", "label": "Past 30 Days", "days": 30},
    {"id": "past_3_months", "label": "Past 3 Months", "months": 3},
    {"id": "past_6_months", "label": "Past 6 Months", "months": 6},
    {"id": "past_1_year", "label": "Past 1 Year", "months": 12},
    {"id": "current_month", "label": "Current Month"},
]


def _parse_date_param(value: str | None, field_label: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_label} must be YYYY-MM-DD.") from exc


def _subtract_months(anchor: date, months: int) -> date:
    year = anchor.year
    month = anchor.month - months
    day = anchor.day
    while month <= 0:
        month += 12
        year -= 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _resolve_quick_range(identifier: str | None, today: date) -> tuple[date | None, date | None, str | None]:
    if not identifier:
        return None, None, None
    # Special-case current month
    if identifier == "current_month":
        start = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = date(today.year, today.month, last_day)
        return start, end, identifier
    for option in QUICK_RANGE_OPTIONS:
        if option["id"] != identifier:
            continue
        if "days" in option:
            days = option["days"]
            start = today - timedelta(days=days - 1)
            return start, today, option["id"]
        months = option.get("months", 0)
        start = _subtract_months(today, months)
        return start, today, option["id"]
    return None, None, None


def _run_cycle_date(run) -> date:
    return date(run.target_year, run.target_month, 1)


def _within_range(candidate: date, start: date | None, end: date | None) -> bool:
    if start and candidate < start:
        return False
    if end and candidate > end:
        return False
    return True


def _filter_runs_by_range(runs: Sequence, start: date | None, end: date | None) -> list:
    filtered: list = []
    for run in runs:
        cycle_date = _run_cycle_date(run)
        if _within_range(cycle_date, start, end):
            filtered.append(run)
    return filtered


def _format_range_label(start: date | None, end: date | None, fallback: str) -> str:
    if start and end:
        return f"{format_display_date(start)} – {format_display_date(end)}"
    if start:
        return f"Since {format_display_date(start)}"
    if end:
        return f"Through {format_display_date(end)}"
    return fallback


def _build_run_card(run_obj, zero: Decimal) -> dict[str, object]:
    frequency_counts = getattr(run_obj, "frequency_counts", None)
    if not isinstance(frequency_counts, dict):
        try:
            frequency_counts = json.loads(run_obj.summary_frequency_counts)
        except (json.JSONDecodeError, AttributeError):
            frequency_counts = {}

    outstanding = getattr(run_obj, "unpaid_total", zero) or zero
    paid_total_value = getattr(run_obj, "paid_total", zero) or zero
    total_value = (
        getattr(run_obj, "computed_total_payout", None)
        or getattr(run_obj, "summary_total_payout", zero)
        or zero
    )
    status = "Completed" if outstanding <= zero else "Needs Attention"
    status_variant = "success" if status == "Completed" else "warning"
    cycle_label = date(run_obj.target_year, run_obj.target_month, 1).strftime("%b %Y")

    return {
        "id": run_obj.id,
        "cycle": cycle_label,
        "created": format_display_date(run_obj.created_at),
        "models_paid": getattr(run_obj, "summary_models_paid", 0) or 0,
        "total": total_value,
        "paid": paid_total_value,
        "outstanding": outstanding,
        "status": status,
        "status_variant": status_variant,
        "frequency_counts": frequency_counts,
        "currency": getattr(run_obj, "currency", "USD"),
    }


def _summarize_adhoc_payments(payments: Sequence[AdhocPayment]) -> dict[str, object]:
    zero = Decimal("0")
    status_keys = ("pending", "paid", "cancelled")
    status_counts: dict[str, int] = {key: 0 for key in status_keys}
    amount_by_status: dict[str, Decimal] = {key: zero for key in status_keys}
    latest_pay_date: date | None = None
    impacted_models: set[int] = set()

    for payment in payments:
        status = (payment.status or "pending").lower()
        if status not in status_counts:
            status_counts[status] = 0
            amount_by_status[status] = zero
        status_counts[status] += 1
        amount_by_status[status] = amount_by_status[status] + payment.amount
        if latest_pay_date is None or payment.pay_date > latest_pay_date:
            latest_pay_date = payment.pay_date
        impacted_models.add(payment.model_id)

    pending_total = amount_by_status.get("pending", zero)
    paid_total = amount_by_status.get("paid", zero)
    cancelled_total = amount_by_status.get("cancelled", zero)
    total_amount = pending_total + paid_total

    return {
        "count": len(payments),
        "models_impacted": len(impacted_models),
        "status_counts": status_counts,
        "amount_by_status": amount_by_status,
        "total_amount": total_amount,
        "pending_total": pending_total,
        "paid_total": paid_total,
        "cancelled_total": cancelled_total,
        "latest_pay_date": latest_pay_date,
        "has_pending": pending_total > zero,
    }


def _compute_frequency_counts(db: Session, run_id: int) -> dict[str, int]:
    rows = (
        db.query(Payout.payment_frequency, func.count(func.distinct(Payout.code)))
        .filter(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .group_by(Payout.payment_frequency)
        .all()
    )
    counts: dict[str, int] = {}
    for frequency, count in rows:
        label = frequency or "unspecified"
        counts[label] = int(count or 0)
    return counts


def _count_unique_models(db: Session, run_ids: list[int]) -> int:
    if not run_ids:
        return 0
    return (
        db.query(func.count(func.distinct(Payout.code)))
        .filter(
            Payout.schedule_run_id.in_(run_ids),
            Payout.model_id.isnot(None),
        )
        .scalar()
        or 0
    )


def _ensure_current_month_run(db: Session, runs: Sequence[Any]) -> list[Any]:
    """Return existing runs without creating automatic placeholders.

    Accepts any sequence of ScheduleRun and returns a concrete list for downstream processing.
    """
    return list(runs)


def _prepare_runs_by_year(db: Session, target_year: int) -> tuple[list, list[int], list]:
    all_runs = _ensure_current_month_run(db, crud.list_schedule_runs(db))

    runs_for_year: list = []
    filtered_runs: list = []
    year_set: set[int] = set()

    zero = Decimal("0")

    for run in all_runs:
        try:
            run.frequency_counts = json.loads(run.summary_frequency_counts)
        except json.JSONDecodeError:
            run.frequency_counts = {}

        summary = crud.run_payment_summary(db, run.id)
        run.summary_models_paid = summary.get("paid_models", 0)
        run.paid_total = summary.get("paid_total", Decimal("0"))
        run.unpaid_total = summary.get("unpaid_total", Decimal("0"))
        run.frequency_counts = _compute_frequency_counts(db, run.id)
        computed_total = summary.get("total_payout", run.paid_total + run.unpaid_total)
        run.computed_total_payout = computed_total
        run.summary_total_payout = computed_total

        total_value = computed_total or zero
        has_activity = (
            total_value > zero
            or run.paid_total > zero
            or run.unpaid_total > zero
            or (run.summary_models_paid or 0) > 0
            or any(run.frequency_counts.values())
        )
        if not has_activity:
            continue

        filtered_runs.append(run)
        year_set.add(run.target_year)

        if run.target_year == target_year:
            runs_for_year.append(run)

    runs_for_year.sort(key=lambda r: (r.target_month, r.created_at), reverse=True)

    available_years = sorted(year_set, reverse=True)

    return runs_for_year, available_years, filtered_runs


def _format_frequency_summary(frequency_counts: object | None) -> str:
    # Accept flexible input; if not a dict[str, int], return empty string
    if not isinstance(frequency_counts, dict):
        return ""
    parts = []
    for name, count in sorted(frequency_counts.items()):
        label = (name or "unspecified").replace("_", " ").title()
        parts.append(f"{label} {count}")
    return ", ".join(parts)


def _gather_dashboard_data(db: Session, month: str | None, year: int | None = None) -> dict[str, object]:
    """Collect the datasets needed to render or export the schedules dashboard."""

    today = date.today()
    display_year = year if year else today.year
    normalized_month = month.strip() if month else ""
    month_candidate: tuple[int, int] | None = None

    if normalized_month:
        try:
            year_str, month_str = normalized_month.split("-")
            year_value = int(year_str)
            month_value = int(month_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Month must be in YYYY-MM format.") from exc
        if not 1 <= month_value <= 12:
            raise HTTPException(status_code=400, detail="Month must be in YYYY-MM format.")
        month_candidate = (year_value, month_value)

    all_runs = _ensure_current_month_run(db, crud.list_schedule_runs(db))

    zero = Decimal("0")

    grouped_runs: dict[tuple[int, int], list] = {}
    filtered_runs: list = []
    for run in all_runs:
        try:
            run.frequency_counts = json.loads(run.summary_frequency_counts)
        except json.JSONDecodeError:
            run.frequency_counts = {}

        summary = crud.run_payment_summary(db, run.id)
        run.summary_models_paid = summary.get("paid_models", 0)
        run.paid_total = summary.get("paid_total", Decimal("0"))
        run.unpaid_total = summary.get("unpaid_total", Decimal("0"))
        run.frequency_counts = _compute_frequency_counts(db, run.id)
        computed_total = summary.get("total_payout", run.paid_total + run.unpaid_total)
        run.computed_total_payout = computed_total
        run.summary_total_payout = computed_total

        total_value = computed_total or zero
        has_activity = (
            total_value > zero
            or run.paid_total > zero
            or run.unpaid_total > zero
            or (run.summary_models_paid or 0) > 0
            or any(run.frequency_counts.values())
        )
        if not has_activity:
            continue

        key = (run.target_year, run.target_month)
        grouped_runs.setdefault(key, []).append(run)
        filtered_runs.append(run)

    all_runs = filtered_runs

    sorted_keys = sorted(grouped_runs.keys(), reverse=True)

    selected_key: tuple[int, int] | None = None
    if month_candidate:
        selected_key = month_candidate
    else:
        year_specific_keys = [key for key in sorted_keys if key[0] == display_year]
        if year_specific_keys:
            selected_key = year_specific_keys[0]
        elif sorted_keys:
            selected_key = sorted_keys[0]

    selected_runs = grouped_runs.get(selected_key, []) if selected_key else []
    selected_run_ids = [run.id for run in selected_runs]

    monthly_frequency: dict[str, int] = {}
    if selected_run_ids:
        frequency_rows = (
            db.query(Payout.payment_frequency, func.count(func.distinct(Payout.code)))
            .filter(
                Payout.schedule_run_id.in_(selected_run_ids),
                Payout.model_id.isnot(None),
            )
            .group_by(Payout.payment_frequency)
            .order_by(Payout.payment_frequency)
            .all()
        )
        for frequency, count in frequency_rows:
            label = frequency or "unspecified"
            monthly_frequency[label] = int(count or 0)

    unique_models = _count_unique_models(db, selected_run_ids)

    total_payout = sum(
        [
            (
                getattr(run, "computed_total_payout", None)
                or getattr(run, "summary_total_payout", zero)
                or zero
            )
            for run in selected_runs
        ],
        zero,
    )
    # Ignore payouts that have become orphaned (model deleted) by relying on run.paid_total/unpaid_total
    # which already exclude rows with model_id is NULL. This prevents inflated totals after deletions.
    paid_total = sum(((getattr(run, "paid_total", zero) or zero) for run in selected_runs), zero)
    unpaid_total = sum(((getattr(run, "unpaid_total", zero) or zero) for run in selected_runs), zero)

    monthly_summary = {
        "run_count": len(selected_runs),
        "models_paid": unique_models,
        "total_payout": total_payout,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
    }

    month_options = []
    for year_value, month_value in sorted_keys:
        if year_value != display_year:
            continue
        value = f"{year_value:04d}-{month_value:02d}"
        # Use short month label (e.g., 'Oct') for the year-at-a-glance chips
        label = date(year_value, month_value, 1).strftime("%b")
        month_options.append(
            {
                "value": value,
                "label": label,
                "run_count": len(grouped_runs[(year_value, month_value)]),
            }
        )

    if month_candidate and month_candidate not in grouped_runs:
        value = f"{month_candidate[0]:04d}-{month_candidate[1]:02d}"
        label = date(month_candidate[0], month_candidate[1], 1).strftime("%b")
        month_options.insert(0, {"value": value, "label": label, "run_count": 0})

    selected_month_value = ""
    selected_month_label = ""
    selected_month_short_label = ""
    selected_month_year_label = ""
    if selected_key:
        selected_month_value = f"{selected_key[0]:04d}-{selected_key[1]:02d}"
        selected_month_date = date(selected_key[0], selected_key[1], 1)
    else:
        selected_month_date = date(today.year, today.month, 1)
    selected_month_label = format_display_date(selected_month_date)
    selected_month_short_label = selected_month_date.strftime("%b")
    selected_month_year_label = selected_month_date.strftime("%b %Y")

    if selected_key:
        adhoc_year, adhoc_month = selected_key
    elif month_candidate:
        adhoc_year, adhoc_month = month_candidate
    else:
        adhoc_year, adhoc_month = today.year, today.month

    monthly_adhoc_payments = crud.list_adhoc_payments_for_month(db, adhoc_year, adhoc_month)
    monthly_adhoc_single = monthly_adhoc_payments[0] if len(monthly_adhoc_payments) == 1 else None
    monthly_adhoc_summary = _summarize_adhoc_payments(monthly_adhoc_payments)
    adhoc_month_label = date(adhoc_year, adhoc_month, 1).strftime("%b")
    adhoc_month_value = f"{adhoc_year:04d}-{adhoc_month:02d}"
    latest_pay_date = monthly_adhoc_summary.get("latest_pay_date")
    monthly_adhoc_summary.update(
        {
            "month_label": adhoc_month_label,
            "month_value": adhoc_month_value,
            "currency": monthly_summary.get("currency") or "USD",
            "latest_pay_date_display": format_display_date(latest_pay_date),
        }
    )
    # Safely extract status dicts for typing
    status_counts = cast(dict[str, int], monthly_adhoc_summary.get("status_counts", {}))
    amount_by_status = cast(dict[str, Decimal], monthly_adhoc_summary.get("amount_by_status", {}))

    status_display = []
    for status_key, status_label in (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ):
        status_display.append(
            {
                "key": status_key,
                "label": status_label,
                "count": status_counts.get(status_key, 0),
                "amount": amount_by_status.get(status_key, zero),
            }
        )
    monthly_adhoc_summary["status_display"] = status_display
    monthly_adhoc_summary["has_payments"] = bool(monthly_adhoc_summary.get("count", 0))

    for option in month_options:
        option["is_selected"] = option["value"] == selected_month_value

    today_key = (today.year, today.month)

    sorted_runs = sorted(
        all_runs,
        key=lambda item: (item.target_year, item.target_month, item.created_at),
        reverse=True,
    )

    recent_runs = [run for run in sorted_runs if (run.target_year, run.target_month) < today_key][:4]

    recent_cards = [_build_run_card(run, zero) for run in recent_runs]
    selected_run_cards = [_build_run_card(run, zero) for run in selected_runs]

    if selected_runs:
        primary_currency = getattr(selected_runs[0], "currency", None)
    elif all_runs:
        primary_currency = getattr(all_runs[0], "currency", None)
    else:
        primary_currency = None

    if not primary_currency and selected_run_cards:
        primary_currency = selected_run_cards[0].get("currency")
    if not primary_currency and recent_cards:
        primary_currency = recent_cards[0].get("currency")

    monthly_summary["currency"] = primary_currency or "USD"

    current_year = display_year
    year_overview = []
    for month_index in range(1, 13):
        key = (current_year, month_index)
        month_label = date(current_year, month_index, 1).strftime("%b")
        count = len(grouped_runs.get(key, []))
        year_overview.append(
            {
                "label": month_label,
                "count": count,
                "value": f"{current_year:04d}-{month_index:02d}",
                "is_current": key == today_key,
                "has_runs": bool(count),
            }
        )

    current_year_runs = [run for run in all_runs if run.target_year == current_year]
    # Sort by period (year, month) descending, then by creation timestamp
    current_year_runs.sort(
        key=lambda item: (item.target_year, item.target_month, item.created_at),
        reverse=True,
    )

    current_year_run_ids = [run.id for run in current_year_runs]
    total_table_payout = sum(
        [
            (
                getattr(run, "computed_total_payout", None)
                or getattr(run, "summary_total_payout", zero)
                or zero
            )
            for run in current_year_runs
        ],
        zero,
    )
    total_table_paid = sum(
        ((getattr(run, "paid_total", zero) or zero) for run in current_year_runs),
        zero,
    )
    total_table_unpaid = sum(
        ((getattr(run, "unpaid_total", zero) or zero) for run in current_year_runs),
        zero,
    )
    unique_models_year = _count_unique_models(db, current_year_run_ids) if current_year_run_ids else 0

    table_currency = None
    for run in current_year_runs:
        table_currency = getattr(run, "currency", None)
        if table_currency:
            break
    if not table_currency:
        table_currency = monthly_summary.get("currency") or "USD"

    for run in current_year_runs:
        run.month_year_label = date(run.target_year, run.target_month, 1).strftime("%b %Y")

    current_year_summary = {
        "run_count": len(current_year_runs),
        "total_payout": total_table_payout,
        "paid_total": total_table_paid,
        "unpaid_total": total_table_unpaid,
        "models_paid": unique_models_year,
        "currency": table_currency,
    }

    return {
        "today": today,
        "current_year": current_year,
        "current_month_label": format_display_date(today),
        "current_month_short_label": today.strftime("%b"),
        "current_month_year_label": today.strftime("%b %Y"),
        "all_runs": all_runs,
        "selected_runs": selected_runs,
        "selected_run_cards": selected_run_cards,
        "recent_run_cards": recent_cards,
        "monthly_summary": monthly_summary,
        "monthly_frequency": monthly_frequency,
        "month_options": month_options,
        "selected_month_value": selected_month_value,
        "selected_month_label": selected_month_label,
        "selected_month_short_label": selected_month_short_label,
        "selected_month_year_label": selected_month_year_label,
        "monthly_adhoc_summary": monthly_adhoc_summary,
        "monthly_adhoc_payments": monthly_adhoc_payments,
        "monthly_adhoc_single": monthly_adhoc_single,
        "year_overview": year_overview,
        "current_year_runs": current_year_runs,
        "current_year_summary": current_year_summary,
        "filters": {"month": selected_month_value},
        "selected_key": selected_key,
        "month_candidate": month_candidate,
        "normalized_month": normalized_month,
    }


@router.get("/")
def list_runs(
    request: Request,
    month: str | None = None,
    show: str | None = None,
    start: str | None = Query(default=None, description="Start date filter (YYYY-MM-DD)"),
    end: str | None = Query(default=None, description="End date filter (YYYY-MM-DD)"),
    year: int = Query(default=None, description="Target year to display"),
    range: str | None = Query(default=None, description="Quick range identifier"),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    target_year = year or today.year
    
    dashboard = _gather_dashboard_data(db, month, target_year)

    # Apply year and range filtering to current_year_runs
    all_runs_unfiltered = cast(list[Any], dashboard["current_year_runs"])  # type: ignore[assignment]

    clear_requested = request.query_params.get("clear") == "1"

    start_input = _parse_date_param(start, "Start date")
    end_input = _parse_date_param(end, "End date")
    if start_input and end_input and end_input < start_input:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")

    # Parse quick range filter
    preset_start, preset_end, active_preset = _resolve_quick_range(range, today)

    effective_start = preset_start if active_preset else start_input
    effective_end = preset_end if active_preset else end_input

    # Do not apply an implicit current-month filter by default; show all cycles for the selected year
    default_filter_applied = False

    filter_active = bool(active_preset or start_input or end_input or default_filter_applied)
    if clear_requested:
        filter_active = False

    if filter_active and (effective_start or effective_end):
        filtered_runs = _filter_runs_by_range(all_runs_unfiltered, effective_start, effective_end)
    else:
        filtered_runs = [run for run in all_runs_unfiltered if run.target_year == target_year]

    # Sort by period (year, month) descending for consistent export ordering
    filtered_runs.sort(
        key=lambda run: (run.target_year, run.target_month, getattr(run, "created_at", datetime.min)),
        reverse=True,
    )

    # Sort the table by period (newest to oldest)
    filtered_runs.sort(
        key=lambda run: (run.target_year, run.target_month, getattr(run, "created_at", datetime.min)),
        reverse=True,
    )
    
    # Recalculate summary for filtered runs
    zero = Decimal("0")
    filtered_run_ids = [run.id for run in filtered_runs]
    filtered_total_payout = sum(
        [
            (
                getattr(run, "computed_total_payout", None)
                or getattr(run, "summary_total_payout", zero)
                or zero
            )
            for run in filtered_runs
        ],
        zero,
    )
    filtered_paid_total = sum(
        ((getattr(run, "paid_total", zero) or zero) for run in filtered_runs),
        zero,
    )
    filtered_unpaid_total = sum(
        ((getattr(run, "unpaid_total", zero) or zero) for run in filtered_runs),
        zero,
    )
    filtered_models_paid = _count_unique_models(db, filtered_run_ids) if filtered_run_ids else 0
    
    filtered_currency = None
    for run in filtered_runs:
        filtered_currency = getattr(run, "currency", None)
        if filtered_currency:
            break
    if not filtered_currency:
        curr_summary = cast(dict[str, object], dashboard["current_year_summary"])  # type: ignore[assignment]
        filtered_currency = cast(str | None, curr_summary.get("currency")) or "USD"
    
    filtered_summary = {
        "run_count": len(filtered_runs),
        "total_payout": filtered_total_payout,
        "paid_total": filtered_paid_total,
        "unpaid_total": filtered_unpaid_total,
        "models_paid": filtered_models_paid,
        "currency": filtered_currency,
    }
    
    if active_preset:
        filter_start_value = preset_start.isoformat() if preset_start else ""
        filter_end_value = preset_end.isoformat() if preset_end else ""
    elif start_input or end_input:
        filter_start_value = start_input.isoformat() if start_input else ""
        filter_end_value = end_input.isoformat() if end_input else ""
    elif default_filter_applied and not clear_requested:
        filter_start_value = effective_start.isoformat() if effective_start else ""
        filter_end_value = effective_end.isoformat() if effective_end else ""
    else:
        filter_start_value = ""
        filter_end_value = ""

    if filter_active:
        adhoc_range_start = effective_start
        adhoc_range_end = effective_end
    else:
        adhoc_range_start = date(target_year, 1, 1)
        adhoc_range_end = date(target_year, 12, 31)

    adhoc_query = (
        db.query(AdhocPayment)
        .options(joinedload(AdhocPayment.model))
        .order_by(AdhocPayment.pay_date.desc(), AdhocPayment.id.desc())
    )
    if adhoc_range_start:
        adhoc_query = adhoc_query.filter(AdhocPayment.pay_date >= adhoc_range_start)
    if adhoc_range_end:
        adhoc_query = adhoc_query.filter(AdhocPayment.pay_date <= adhoc_range_end)

    filtered_adhoc_payments = adhoc_query.all()
    filtered_adhoc_summary = _summarize_adhoc_payments(filtered_adhoc_payments)
    monthly_adhoc_summary_ctx = cast(dict[str, object], dashboard.get("monthly_adhoc_summary", {}))
    filtered_adhoc_summary["currency"] = cast(str | None, monthly_adhoc_summary_ctx.get("currency")) or "USD"
    filtered_adhoc_summary["has_payments"] = bool(filtered_adhoc_summary.get("count", 0))

    # Build available years for dropdown
    all_available_runs = cast(list[Any], dashboard["all_runs"])  # type: ignore[assignment]
    available_years = sorted({run.target_year for run in all_available_runs}, reverse=True)
    
    # Build quick range options
    base_params: dict[str, object] = {}
    if target_year != today.year:
        base_params["year"] = target_year
    
    quick_ranges = []
    for option in QUICK_RANGE_OPTIONS:
        params = base_params.copy()
        params["range"] = option["id"]
        quick_ranges.append(
            {
                "id": option["id"],
                "label": option["label"],
                "url": f"/schedules?{urlencode(params)}",
                "is_active": option["id"] == active_preset,
            }
        )
    
    # Determine scope label
    if active_preset and preset_start and preset_end:
        scope_label = _format_range_label(preset_start, preset_end, str(target_year))
    elif default_filter_applied and effective_start and effective_end:
        scope_label = _format_range_label(effective_start, effective_end, str(target_year))
    elif start_input or end_input:
        scope_label = _format_range_label(start_input, end_input, str(target_year))
    else:
        scope_label = str(target_year)

    clear_params: dict[str, object] = {}
    if target_year != today.year:
        clear_params["year"] = target_year
    clear_params["clear"] = "1"
    clear_filter_url = f"/schedules?{urlencode(clear_params)}"

    adhoc_filter_params: dict[str, object] = {}
    if active_preset:
        adhoc_filter_params["quick_range"] = active_preset
    else:
        if filter_active and effective_start:
            adhoc_filter_params["start_date"] = effective_start.isoformat()
        if filter_active and effective_end:
            adhoc_filter_params["end_date"] = effective_end.isoformat()
    adhoc_filter_url = "/schedules/adhoc"
    if adhoc_filter_params:
        adhoc_filter_url = f"{adhoc_filter_url}?{urlencode(adhoc_filter_params)}"

    # Current month quickfilter URL
    current_month_params: dict[str, object] = {}
    if target_year != today.year:
        current_month_params["year"] = target_year
    current_month_params["range"] = "current_month"
    current_month_url = f"/schedules?{urlencode(current_month_params)}"

    export_params: dict[str, object] = {"year": target_year}
    if active_preset:
        export_params["range"] = active_preset
    elif filter_active:
        if effective_start:
            export_params["start"] = effective_start.isoformat()
        if effective_end:
            export_params["end"] = effective_end.isoformat()
    export_query = urlencode(export_params)
    export_url = "/schedules/all-table/export"
    if export_query:
        export_url = f"{export_url}?{export_query}"

    monthly_adhoc_summary_for_defaults = cast(dict[str, object], dashboard.get("monthly_adhoc_summary", {}))
    monthly_adhoc_count = int(monthly_adhoc_summary_for_defaults.get("count", 0) or 0)
    export_defaults = {
        "monthly_summary": True,
        "run_details": bool(dashboard["selected_runs"]),
        "adhoc_summary": monthly_adhoc_count > 0,
        "adhoc_details": monthly_adhoc_count > 0,
        "recent_runs": bool(dashboard["recent_run_cards"]),
    }

    # Aggregate counts for overdue and on-hold payouts
    overdue_count = (
        db.query(func.count(Payout.id))
        .filter(
            Payout.status.in_(["not_paid", "on_hold"]),
            Payout.pay_date.isnot(None),
            Payout.pay_date < today,
        )
        .scalar()
        or 0
    )

    on_hold_count = (
        db.query(func.count(Payout.id))
        .filter(Payout.status == "on_hold")
        .scalar()
        or 0
    )

    on_hold_overdue_count = (
        db.query(func.count(Payout.id))
        .filter(
            Payout.status == "on_hold",
            Payout.pay_date.isnot(None),
            Payout.pay_date < today,
        )
        .scalar()
        or 0
    )

    overdue_target_run_id = (
        db.query(Payout.schedule_run_id)
        .filter(
            Payout.status.in_(["not_paid", "on_hold"]),
            Payout.pay_date.isnot(None),
            Payout.pay_date < today,
            Payout.schedule_run_id.isnot(None),
        )
        .order_by(Payout.pay_date.asc())
        .limit(1)
        .scalar()
    )

    on_hold_target_run_id = (
        db.query(Payout.schedule_run_id)
        .filter(
            Payout.status == "on_hold",
            Payout.pay_date.isnot(None),
            Payout.pay_date < today,
            Payout.schedule_run_id.isnot(None),
        )
        .order_by(Payout.pay_date.asc())
        .limit(1)
        .scalar()
    )

    overdue_filter_params: dict[str, object] = {"show": "overdue"}
    if target_year != today.year:
        overdue_filter_params["year"] = target_year
    if active_preset:
        overdue_filter_params["range"] = active_preset
    elif filter_active:
        if effective_start:
            overdue_filter_params["start"] = effective_start.isoformat()
        if effective_end:
            overdue_filter_params["end"] = effective_end.isoformat()

    overdue_query = urlencode(overdue_filter_params)
    overdue_query_suffix = f"?{overdue_query}" if overdue_query else ""
    overdue_fallback_url = f"/schedules{overdue_query_suffix}"

    # Always prefer a consolidated current-month overdue view so users see full scope
    overdue_target_url = f"/schedules?range=current_month&show=overdue"

    compliance_filter_params: dict[str, object] = {"show": "compliance"}
    if target_year != today.year:
        compliance_filter_params["year"] = target_year
    if active_preset:
        compliance_filter_params["range"] = active_preset
    elif filter_active:
        if effective_start:
            compliance_filter_params["start"] = effective_start.isoformat()
        if effective_end:
            compliance_filter_params["end"] = effective_end.isoformat()

    compliance_query = urlencode(compliance_filter_params)
    compliance_query_suffix = f"?{compliance_query}" if compliance_query else ""
    compliance_fallback_url = f"/schedules{compliance_query_suffix}"

    compliance_target_url = (
        f"/schedules/{on_hold_target_run_id}?status=on_hold"
        if on_hold_target_run_id
        else compliance_fallback_url
    )

    # Fetch overdue and on-hold payments if requested
    overdue_payments: list[dict[str, object]] = []
    on_hold_payments: list[dict[str, object]] = []
    compliance_payments: list[dict[str, object]] = []
    
    if show == "overdue":
        from sqlalchemy import select
        stmt = (
            select(Payout, Model)
            .join(Model, Payout.model_id == Model.id)
            .where(
                Payout.status.in_(["not_paid", "on_hold"]),
                Payout.pay_date < today
            )
            .order_by(Payout.pay_date.asc())
        )
        results = db.execute(stmt).all()
        for payout, model in results:
            overdue_payments.append({
                "id": payout.id,
                "pay_date": payout.pay_date,
                "amount": payout.amount,
                "status": payout.status,
                "notes": payout.notes,
                "model_code": model.code,
                "model_name": model.working_name,
                "run_id": payout.schedule_run_id,
            })
    
    if show == "on_hold":
        from sqlalchemy import select
        stmt = (
            select(Payout, Model)
            .join(Model, Payout.model_id == Model.id)
            .where(Payout.status == "on_hold")
            .order_by(Payout.pay_date.asc())
        )
        results = db.execute(stmt).all()
        for payout, model in results:
            on_hold_payments.append({
                "id": payout.id,
                "pay_date": payout.pay_date,
                "amount": payout.amount,
                "status": payout.status,
                "notes": payout.notes,
                "model_code": model.code,
                "model_name": model.working_name,
                "run_id": payout.schedule_run_id,
            })

    if show == "compliance":
        from sqlalchemy import select
        stmt = (
            select(Payout, Model)
            .join(Model, Payout.model_id == Model.id)
            .where(
                Payout.status == "on_hold",
                Payout.pay_date.isnot(None),
                Payout.pay_date < today,
            )
            .order_by(Payout.pay_date.asc())
        )
        results = db.execute(stmt).all()
        for payout, model in results:
            compliance_payments.append({
                "id": payout.id,
                "pay_date": payout.pay_date,
                "amount": payout.amount,
                "status": payout.status,
                "notes": payout.notes,
                "model_code": model.code,
                "model_name": model.working_name,
                "run_id": payout.schedule_run_id,
            })

    return templates.TemplateResponse(
        "schedules/list.html",
        {
            "request": request,
            "user": user,
            "runs": dashboard["selected_runs"],
            "filters": dashboard["filters"],
            "month_options": dashboard["month_options"],
            "selected_month_label": dashboard["selected_month_label"],
            "selected_month_short_label": dashboard["selected_month_short_label"],
            "selected_month_year_label": dashboard["selected_month_year_label"],
            "current_month_label": dashboard["current_month_label"],
            "current_month_year_label": dashboard["current_month_year_label"],
            "monthly_summary": dashboard["monthly_summary"],
            "monthly_frequency": dashboard["monthly_frequency"],
            "has_runs": bool(dashboard["all_runs"]),
            "recent_runs": dashboard["recent_run_cards"],
            "selected_run_cards": dashboard["selected_run_cards"],
            "monthly_adhoc_summary": dashboard["monthly_adhoc_summary"],
            "monthly_adhoc_payments": dashboard["monthly_adhoc_payments"],
            "monthly_adhoc_single": dashboard["monthly_adhoc_single"],
            "year_overview": dashboard["year_overview"],
            "current_year": dashboard["current_year"],
            "view_all_url": f"/schedules/all?year={dashboard['current_year']}",
            "table_view_url": f"/schedules/all-table?year={dashboard['current_year']}",
            "export_url": export_url,
            "current_year_runs": filtered_runs,
            "current_year_summary": filtered_summary,
            "export_defaults": export_defaults,
            "export_month_value": dashboard["selected_month_value"],
            "show_filter": show,
            "overdue_payments": overdue_payments,
            "on_hold_payments": on_hold_payments,
            "compliance_payments": compliance_payments,
            "available_years": available_years,
            "selected_year": target_year,
            "quick_ranges": quick_ranges,
            "filter_active": filter_active,
            "active_preset": active_preset,
            "scope_label": scope_label,
            "filter_start_value": filter_start_value,
            "filter_end_value": filter_end_value,
            "clear_filter_url": clear_filter_url,
            "has_custom_range": bool(start_input or end_input),
            "filtered_adhoc_summary": filtered_adhoc_summary,
            "adhoc_filter_url": adhoc_filter_url,
            "current_month_url": current_month_url,
            "overdue_count": overdue_count,
            "on_hold_count": on_hold_count,
            "on_hold_overdue_count": on_hold_overdue_count,
            "overdue_target_url": overdue_target_url,
            "compliance_target_url": compliance_target_url,
        },
    )


@router.get("/adhoc")
def view_adhoc_payments(
    request: Request,
    month: str | None = None,  # Keep for backward compatibility but not used for filtering
    status: list[str] | None = Query(None),
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    quick_range: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    sort: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Get all adhoc payments instead of monthly filtered ones
    all_adhoc_payments = (
        db.query(AdhocPayment)
        .options(joinedload(AdhocPayment.model))
        .order_by(AdhocPayment.pay_date.desc(), AdhocPayment.id.desc())
        .all()
    )

    status_filters = {value.lower() for value in status or [] if value}
    search_term = (search or "").strip()

    parsed_start = _parse_date_param(start_date, "Start date")
    parsed_end = _parse_date_param(end_date, "End date")

    quick_start, quick_end, quick_identifier = _resolve_quick_range(quick_range, date.today())
    if quick_identifier:
        parsed_start = quick_start
        parsed_end = quick_end

    try:
        min_amount_value = Decimal(min_amount) if min_amount else None
    except (ArithmeticError, ValueError):
        raise HTTPException(status_code=400, detail="Minimum amount must be numeric.") from None

    try:
        max_amount_value = Decimal(max_amount) if max_amount else None
    except (ArithmeticError, ValueError):
        raise HTTPException(status_code=400, detail="Maximum amount must be numeric.") from None

    if min_amount_value and max_amount_value and min_amount_value > max_amount_value:
        raise HTTPException(status_code=400, detail="Minimum amount cannot exceed maximum amount.")

    valid_statuses = ["pending", "paid", "cancelled"]
    normalized_status_filters = [option for option in valid_statuses if option in status_filters]

    payments = list(all_adhoc_payments)
    filtered_payments: list[AdhocPayment] = []
    lowered_search = search_term.lower()

    for payment in payments:
        status_value = (payment.status or "pending").lower()
        if normalized_status_filters and status_value not in normalized_status_filters:
            continue

        if lowered_search:
            model = getattr(payment, "model", None)
            model_code = (getattr(model, "code", "") or "").lower()
            model_name = (getattr(model, "working_name", "") or "").lower()
            description_text = (payment.description or "").lower()
            notes_text = (payment.notes or "").lower()
            if lowered_search not in model_code and lowered_search not in model_name and lowered_search not in description_text and lowered_search not in notes_text:
                continue

        if parsed_start and payment.pay_date < parsed_start:
            continue
        if parsed_end and payment.pay_date > parsed_end:
            continue

        if min_amount_value and payment.amount < min_amount_value:
            continue
        if max_amount_value and payment.amount > max_amount_value:
            continue

        filtered_payments.append(payment)

    sort_order = (sort or "pay_date_desc").lower()

    def _sort_key(item: AdhocPayment):
        if sort_order == "pay_date_asc":
            return (item.pay_date, item.id)
        if sort_order == "amount_desc":
            return (-item.amount, item.pay_date, item.id)
        if sort_order == "amount_asc":
            return (item.amount, item.pay_date, item.id)
        if sort_order == "status":
            return ((item.status or "").lower(), item.pay_date, item.id)
        return (-item.pay_date.toordinal(), item.id)

    filtered_payments.sort(key=_sort_key)

    # Compute summary from all filtered payments
    filtered_summary = _summarize_adhoc_payments(filtered_payments)
    # Compute summary from all payments for total stats
    all_summary = _summarize_adhoc_payments(all_adhoc_payments)
    currency = "USD"
    all_summary.update({
        "month_label": "All Time",
        "currency": currency,
        "has_payments": len(all_adhoc_payments) > 0,
    })
    filtered_summary.update(
        {
            "month_label": "All Time",
            "currency": currency,
        }
    )

    # Safely access nested dicts for type checking
    f_status_counts = cast(dict[str, int], filtered_summary.get("status_counts", {}))
    f_amount_by_status = cast(dict[str, Decimal], filtered_summary.get("amount_by_status", {}))

    filtered_status_display = []
    for status_key, status_label in (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ):
        filtered_status_display.append(
            {
                "key": status_key,
                "label": status_label,
                "count": f_status_counts.get(status_key, 0),
                "amount": f_amount_by_status.get(status_key, Decimal("0")),
            }
        )
    filtered_summary["status_display"] = filtered_status_display
    filtered_summary["has_payments"] = bool(filtered_summary.get("count", 0))

    status_options = [
        {"value": "pending", "label": "Pending"},
        {"value": "paid", "label": "Paid"},
        {"value": "cancelled", "label": "Cancelled"},
    ]

    filters_payload = {
        "month": None,  # Not used anymore
        "status": normalized_status_filters,
        "search": search_term,
        "start_date": parsed_start.isoformat() if parsed_start else "",
        "end_date": parsed_end.isoformat() if parsed_end else "",
        "quick_range": quick_identifier or (quick_range or ""),
        "min_amount": str(min_amount_value) if min_amount_value is not None else "",
        "max_amount": str(max_amount_value) if max_amount_value is not None else "",
        "sort": sort_order,
    }

    active_filter_chips: list[dict[str, str]] = []
    if search_term:
        active_filter_chips.append({"label": f"Search: {search_term}"})

    if normalized_status_filters and len(normalized_status_filters) < len(status_options):
        labels = [opt["label"] for opt in status_options if opt["value"] in normalized_status_filters]
        active_filter_chips.append({"label": f"Status: {', '.join(labels)}"})

    if parsed_start and parsed_end:
        active_filter_chips.append({"label": f"Pay Date: {parsed_start.isoformat()} – {parsed_end.isoformat()}"})
    elif parsed_start:
        active_filter_chips.append({"label": f"Pay Date ≥ {parsed_start.isoformat()}"})
    elif parsed_end:
        active_filter_chips.append({"label": f"Pay Date ≤ {parsed_end.isoformat()}"})

    if quick_identifier:
        option = next((item for item in QUICK_RANGE_OPTIONS if item["id"] == quick_identifier), None)
        if option:
            active_filter_chips.append({"label": f"Range: {option['label']}"})

    if min_amount_value is not None and max_amount_value is not None:
        active_filter_chips.append({"label": f"Amount: {min_amount_value} – {max_amount_value}"})
    elif min_amount_value is not None:
        active_filter_chips.append({"label": f"Amount ≥ {min_amount_value}"})
    elif max_amount_value is not None:
        active_filter_chips.append({"label": f"Amount ≤ {max_amount_value}"})

    if sort_order and sort_order != "pay_date_desc":
        sort_labels = {
            "pay_date_asc": "Sort: Pay Date ↑",
            "amount_desc": "Sort: Amount ↓",
            "amount_asc": "Sort: Amount ↑",
            "status": "Sort: Status",
        }
        label = sort_labels.get(sort_order)
        if label:
            active_filter_chips.append({"label": label})

    quick_range_options = QUICK_RANGE_OPTIONS

    return templates.TemplateResponse(
        "schedules/adhoc.html",
        {
            "request": request,
            "user": user,
            "filters": filters_payload,
            "year_overview": [],  # Not needed without period selector
            "monthly_adhoc_summary": all_summary,  # Use all-time summary
            "monthly_adhoc_payments": filtered_payments,
            "monthly_adhoc_single": None,  # Not needed anymore
            "filtered_adhoc_summary": filtered_summary,
            "status_options": status_options,
            "active_filter_chips": active_filter_chips,
            "quick_range_options": quick_range_options,
        },
    )


@router.post("/export")
def export_dashboard_excel(
    request: Request,
    month: str | None = Form(None),
    include_monthly_summary: bool = Form(False),
    include_run_details: bool = Form(False),
    include_adhoc_summary: bool = Form(False),
    include_adhoc_details: bool = Form(False),
    include_recent_runs: bool = Form(False),
    year_filter: int | None = Form(None),
    start_filter: str | None = Form(None),
    end_filter: str | None = Form(None),
    range_filter: str | None = Form(None),
    year_query: int | None = Query(default=None, alias="year"),
    start_query: str | None = Query(default=None, alias="start"),
    end_query: str | None = Query(default=None, alias="end"),
    range_query: str | None = Query(default=None, alias="range"),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    target_year = year_filter or year_query or today.year

    start_value = start_filter or start_query or request.query_params.get("start")
    end_value = end_filter or end_query or request.query_params.get("end")
    range_value = range_filter or range_query or request.query_params.get("range")

    dashboard = _gather_dashboard_data(db, month, target_year)

    options = {
        "monthly_summary": include_monthly_summary,
        "run_details": include_run_details,
        "adhoc_summary": include_adhoc_summary,
        "adhoc_details": include_adhoc_details,
        "recent_runs": include_recent_runs,
    }

    if not any(options.values()):
        raise HTTPException(status_code=400, detail="Select at least one dataset to export.")

    start_input = _parse_date_param(start_value, "Start date")
    end_input = _parse_date_param(end_value, "End date")
    if start_input and end_input and end_input < start_input:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")

    preset_start, preset_end, active_preset = _resolve_quick_range(range_value, today)
    effective_start = preset_start if active_preset else start_input
    effective_end = preset_end if active_preset else end_input

    filter_active = bool(active_preset or start_input or end_input)

    all_runs_unfiltered = cast(list[Any], dashboard["current_year_runs"])  # type: ignore[assignment]
    if filter_active and (effective_start or effective_end):
        filtered_runs = _filter_runs_by_range(all_runs_unfiltered, effective_start, effective_end)
    else:
        filtered_runs = [run for run in all_runs_unfiltered if run.target_year == target_year]

    zero = Decimal("0")
    filtered_run_ids = [run.id for run in filtered_runs]
    filtered_total_payout = sum(
        [
            (
                getattr(run, "computed_total_payout", None)
                or getattr(run, "summary_total_payout", zero)
                or zero
            )
            for run in filtered_runs
        ],
        zero,
    )
    filtered_paid_total = sum(((getattr(run, "paid_total", zero) or zero) for run in filtered_runs), zero)
    filtered_unpaid_total = sum(((getattr(run, "unpaid_total", zero) or zero) for run in filtered_runs), zero)
    filtered_models_paid = _count_unique_models(db, filtered_run_ids) if filtered_run_ids else 0

    filtered_currency = None
    for run in filtered_runs:
        filtered_currency = getattr(run, "currency", None)
        if filtered_currency:
            break
    if not filtered_currency:
        curr_summary = cast(dict[str, object], dashboard["current_year_summary"])  # type: ignore[assignment]
        filtered_currency = cast(str | None, curr_summary.get("currency")) or "USD"

    filtered_summary = {
        "run_count": len(filtered_runs),
        "total_payout": filtered_total_payout,
        "paid_total": filtered_paid_total,
        "unpaid_total": filtered_unpaid_total,
        "models_paid": filtered_models_paid,
        "currency": filtered_currency,
    }

    scope_label = _format_range_label(effective_start, effective_end, str(target_year))

    export_run_cards = [_build_run_card(run, zero) for run in filtered_runs]

    if filter_active:
        adhoc_range_start = effective_start
        adhoc_range_end = effective_end
    else:
        adhoc_range_start = date(target_year, 1, 1)
        adhoc_range_end = date(target_year, 12, 31)

    adhoc_query = (
        db.query(AdhocPayment)
        .options(joinedload(AdhocPayment.model))
        .order_by(AdhocPayment.pay_date.desc(), AdhocPayment.id.desc())
    )
    if adhoc_range_start:
        adhoc_query = adhoc_query.filter(AdhocPayment.pay_date >= adhoc_range_start)
    if adhoc_range_end:
        adhoc_query = adhoc_query.filter(AdhocPayment.pay_date <= adhoc_range_end)

    filtered_adhoc_payments = adhoc_query.all()
    filtered_adhoc_summary = _summarize_adhoc_payments(filtered_adhoc_payments)
    filtered_adhoc_summary.update(
        {
            "currency": filtered_currency,
            "month_label": scope_label,
            "has_payments": bool(filtered_adhoc_summary.get("count", 0)),
        }
    )

    f_status_counts = cast(dict[str, int], filtered_adhoc_summary.get("status_counts", {}))
    f_amount_by_status = cast(dict[str, Decimal], filtered_adhoc_summary.get("amount_by_status", {}))
    filtered_status_display = []
    for status_key, status_label in (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ):
        filtered_status_display.append(
            {
                "label": status_label,
                "count": f_status_counts.get(status_key, 0),
                "amount": f_amount_by_status.get(status_key, Decimal("0")),
            }
        )
    filtered_adhoc_summary["status_display"] = filtered_status_display

    def _decimal_to_float(value: object | None) -> float:
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if options["monthly_summary"]:
            summary_rows = [
                {"Metric": "Scope", "Value": scope_label},
                {"Metric": "Cycle Count", "Value": filtered_summary.get("run_count", 0)},
                {"Metric": "Models Paid", "Value": filtered_summary.get("models_paid", 0)},
                {"Metric": "Total Payout", "Value": _decimal_to_float(filtered_summary.get("total_payout"))},
                {"Metric": "Paid Total", "Value": _decimal_to_float(filtered_summary.get("paid_total"))},
                {"Metric": "Outstanding", "Value": _decimal_to_float(filtered_summary.get("unpaid_total"))},
                {"Metric": "Currency", "Value": filtered_summary.get("currency", "USD")},
            ]
            if effective_start:
                summary_rows.append({"Metric": "Filter Start", "Value": effective_start.isoformat()})
            if effective_end:
                summary_rows.append({"Metric": "Filter End", "Value": effective_end.isoformat()})
            if active_preset:
                summary_rows.append({"Metric": "Quick Range", "Value": active_preset})

            summary_df = pd.DataFrame(summary_rows)
            summary_df.to_excel(writer, sheet_name="Monthly Summary", index=False)

            frequency_totals: dict[str, int] = {}
            for card in export_run_cards:
                frequency_counts = card.get("frequency_counts") or {}
                if isinstance(frequency_counts, dict):
                    for label, count in frequency_counts.items():
                        if count:
                            frequency_totals[label] = frequency_totals.get(label, 0) + int(count)

            if frequency_totals:
                freq_rows = [
                    {
                        "Frequency": (label or "unspecified").replace("_", " ").title(),
                        "Models": count,
                    }
                    for label, count in sorted(frequency_totals.items())
                ]
                freq_df = pd.DataFrame(freq_rows)
                freq_df.to_excel(
                    writer,
                    sheet_name="Monthly Summary",
                    index=False,
                    startrow=len(summary_rows) + 2,
                )

        if options["run_details"]:
            cycle_rows: list[dict[str, object]] = []
            for card in export_run_cards:
                cycle_rows.append(
                    {
                        "Cycle ID": card.get("id"),
                        "Cycle": card.get("cycle"),
                        "Created": card.get("created"),
                        "Status": card.get("status"),
                        "Currency": card.get("currency"),
                        "Models Paid": card.get("models_paid"),
                        "Total Payout": _decimal_to_float(card.get("total")),
                        "Paid": _decimal_to_float(card.get("paid")),
                        "Outstanding": _decimal_to_float(card.get("outstanding")),
                        "Frequency Mix": _format_frequency_summary(card.get("frequency_counts")),
                    }
                )
            cycle_columns = [
                "Cycle ID",
                "Cycle",
                "Created",
                "Status",
                "Currency",
                "Models Paid",
                "Total Payout",
                "Paid",
                "Outstanding",
                "Frequency Mix",
            ]
            cycles_df = pd.DataFrame(cycle_rows, columns=cycle_columns)
            cycles_df.to_excel(writer, sheet_name="Cycles", index=False)

        if options["adhoc_summary"]:
            adhoc_summary = filtered_adhoc_summary
            adhoc_rows = [
                {"Metric": "Month", "Value": adhoc_summary.get("month_label", "")},
                {"Metric": "Payments", "Value": adhoc_summary.get("count", 0)},
                {"Metric": "Models Impacted", "Value": adhoc_summary.get("models_impacted", 0)},
                {"Metric": "Total Amount", "Value": _decimal_to_float(adhoc_summary.get("total_amount"))},
                {"Metric": "Pending Amount", "Value": _decimal_to_float(adhoc_summary.get("pending_total"))},
                {"Metric": "Paid Amount", "Value": _decimal_to_float(adhoc_summary.get("paid_total"))},
                {"Metric": "Cancelled Amount", "Value": _decimal_to_float(adhoc_summary.get("cancelled_total"))},
                {"Metric": "Latest Pay Date", "Value": adhoc_summary.get("latest_pay_date_display", "")},
            ]
            adhoc_df = pd.DataFrame(adhoc_rows)
            adhoc_df.to_excel(writer, sheet_name="Adhoc Summary", index=False)

            status_rows = [
                {
                    "Status": item.get("label"),
                    "Count": item.get("count", 0),
                    "Amount": _decimal_to_float(item.get("amount")),
                }
                for item in adhoc_summary.get("status_display", [])
            ]
            if status_rows:
                status_df = pd.DataFrame(status_rows)
                status_df.to_excel(
                    writer,
                    sheet_name="Adhoc Summary",
                    index=False,
                    startrow=len(adhoc_rows) + 2,
                )

        if options["adhoc_details"]:
            adhoc_detail_rows: list[dict[str, object]] = []
            for payment in filtered_adhoc_payments:
                model_code = getattr(payment.model, "code", "") if getattr(payment, "model", None) else ""
                model_name = getattr(payment.model, "working_name", "") if getattr(payment, "model", None) else ""
                adhoc_detail_rows.append(
                    {
                        "Model Code": model_code,
                        "Model Name": model_name,
                        "Pay Date": format_display_date(payment.pay_date),
                        "Amount": _decimal_to_float(payment.amount if hasattr(payment, "amount") else 0),
                        "Status": (payment.status or "").replace("_", " ").title(),
                        "Description": payment.description or "",
                        "Notes": payment.notes or "",
                    }
                )
            adhoc_detail_columns = [
                "Model Code",
                "Model Name",
                "Pay Date",
                "Amount",
                "Status",
                "Description",
                "Notes",
            ]
            adhoc_details_df = pd.DataFrame(adhoc_detail_rows, columns=adhoc_detail_columns)
            adhoc_details_df.to_excel(writer, sheet_name="Adhoc Payments", index=False)

        if options["recent_runs"]:
            recent_rows: list[dict[str, object]] = []
            for card in dashboard["recent_run_cards"]:
                recent_rows.append(
                    {
                        "Cycle ID": card.get("id"),
                        "Cycle": card.get("cycle"),
                        "Created": card.get("created"),
                        "Status": card.get("status"),
                        "Currency": card.get("currency"),
                        "Models Paid": card.get("models_paid"),
                        "Total Payout": _decimal_to_float(card.get("total")),
                        "Paid": _decimal_to_float(card.get("paid")),
                        "Outstanding": _decimal_to_float(card.get("outstanding")),
                    }
                )
            recent_columns = [
                "Cycle ID",
                "Cycle",
                "Created",
                "Status",
                "Currency",
                "Models Paid",
                "Total Payout",
                "Paid",
                "Outstanding",
            ]
            recent_df = pd.DataFrame(recent_rows, columns=recent_columns)
            recent_df.to_excel(writer, sheet_name="Recent Cycles", index=False)

    buffer.seek(0)

    if filter_active:
        filename_label = scope_label
    else:
        filename_label = str(target_year)
    safe_slug = filename_label.replace(" ", "_").replace("/", "-")
    filename = f"payroll_dashboard_{safe_slug}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/all")
def list_runs_all(
    request: Request,
    year: int = Query(default=None, description="Target year to display"),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    target_year = year or today.year

    runs_for_year, available_years, all_runs = _prepare_runs_by_year(db, target_year)

    zero = Decimal("0")
    run_cards = [_build_run_card(run, zero) for run in runs_for_year]

    month_totals_map: dict[str, int] = {}
    for run in run_cards:
        cycle_label = str(run.get("cycle") or "")
        month_totals_map[cycle_label] = month_totals_map.get(cycle_label, 0) + 1

    month_totals: list[dict[str, object]] = []
    for month_index in range(1, 13):
        label = format_display_date(date(target_year, month_index, 1))
        month_value = f"{target_year:04d}-{month_index:02d}"
        count = month_totals_map.get(label, 0)
        month_totals.append(
            {
                "label": label,
                "count": count,
                "month_value": month_value,
                "has_runs": bool(count),
            }
        )

    return templates.TemplateResponse(
        "schedules/all.html",
        {
            "request": request,
            "user": user,
            "year": target_year,
            "runs": run_cards,
            "available_years": available_years,
            "month_totals": month_totals,
            "table_view_url": f"/schedules/all-table?year={target_year}",
        },
    )


@router.get("/all-table")
def list_runs_all_table(
    request: Request,
    year: int = Query(default=None, description="Target year to display"),
    start: str | None = Query(default=None, description="Filter start date (YYYY-MM-DD)"),
    end: str | None = Query(default=None, description="Filter end date (YYYY-MM-DD)"),
    range: str | None = Query(default=None, description="Quick range identifier"),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    target_year = year or today.year

    runs_for_year, available_years, all_runs = _prepare_runs_by_year(db, target_year)

    start_date = _parse_date_param(start, "Start date")
    end_date = _parse_date_param(end, "End date")
    preset_start, preset_end, active_preset = _resolve_quick_range(range, today)

    if active_preset:
        start_date = preset_start
        end_date = preset_end

    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")

    filter_active = bool(start_date or end_date)

    if filter_active:
        display_runs = _filter_runs_by_range(all_runs, start_date, end_date)
    else:
        display_runs = runs_for_year

    display_runs = sorted(display_runs, key=lambda run: run.created_at, reverse=True)

    zero = Decimal("0")
    run_ids = [run.id for run in display_runs]
    total_payout = sum(
        [
            (
                getattr(run, "computed_total_payout", None)
                or getattr(run, "summary_total_payout", zero)
                or zero
            )
            for run in display_runs
        ],
        zero,
    )
    paid_total = sum((getattr(run, "paid_total", zero) or zero) for run in display_runs)
    unpaid_total = sum((getattr(run, "unpaid_total", zero) or zero) for run in display_runs)
    models_paid = _count_unique_models(db, run_ids)

    currency = None
    for run in display_runs:
        currency = getattr(run, "currency", None)
        if currency:
            break
    if not currency:
        if runs_for_year:
            currency = getattr(runs_for_year[0], "currency", None)
        elif all_runs:
            currency = getattr(all_runs[0], "currency", None)

    year_summary = {
        "run_count": len(display_runs),
        "total_payout": total_payout,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "models_paid": models_paid,
        "currency": currency or "USD",
    }

    base_params: dict[str, object] = {}
    if target_year:
        base_params["year"] = target_year

    quick_ranges = []
    for option in QUICK_RANGE_OPTIONS:
        params = base_params.copy()
        params["range"] = option["id"]
        quick_ranges.append(
            {
                "id": option["id"],
                "label": option["label"],
                "url": f"/schedules/all-table?{urlencode(params)}",
                "is_active": option["id"] == active_preset,
            }
        )

    year_buttons = []
    for yr in available_years:
        params = {"year": yr}
        year_buttons.append(
            {
                "label": yr,
                "url": f"/schedules/all-table?{urlencode(params)}",
                "is_selected": yr == target_year,
            }
        )

    filter_start_value = start_date.isoformat() if start_date else ""
    filter_end_value = end_date.isoformat() if end_date else ""

    scope_label = _format_range_label(start_date, end_date, str(target_year))

    export_params = base_params.copy()
    if start_date:
        export_params["start"] = start_date.isoformat()
    if end_date:
        export_params["end"] = end_date.isoformat()
    if active_preset:
        export_params["range"] = active_preset
    export_query = urlencode(export_params)
    export_url = "/schedules/all-table/export"
    if export_query:
        export_url = f"{export_url}?{export_query}"

    clear_url = f"/schedules/all-table?{urlencode(base_params)}" if base_params else "/schedules/all-table"

    # Add month_year_label to each run for display
    for run in display_runs:
        run.month_year_label = date(run.target_year, run.target_month, 1).strftime("%b %Y")

    return templates.TemplateResponse(
        "schedules/all_table.html",
        {
            "request": request,
            "user": user,
            "year": target_year,
            "runs": display_runs,
            "available_years": available_years,
            "year_summary": year_summary,
            "year_buttons": year_buttons,
            "has_previous_years": len(available_years) > 1,
            "card_view_url": f"/schedules/all?year={target_year}",
            "export_url": export_url,
            "quick_ranges": quick_ranges,
            "filter_active": filter_active,
            "filter_start_value": filter_start_value,
            "filter_end_value": filter_end_value,
            "active_preset": active_preset,
            "clear_url": clear_url,
            "scope_label": scope_label,
        },
    )


@router.get("/all-table/export")
def export_runs_all_table(
    year: int = Query(default=None, description="Target year to export"),
    start: str | None = Query(default=None, description="Filter start date (YYYY-MM-DD)"),
    end: str | None = Query(default=None, description="Filter end date (YYYY-MM-DD)"),
    range: str | None = Query(default=None, description="Quick range identifier"),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    target_year = year or today.year

    runs_for_year, _, all_runs = _prepare_runs_by_year(db, target_year)

    start_date = _parse_date_param(start, "Start date")
    end_date = _parse_date_param(end, "End date")
    preset_start, preset_end, active_preset = _resolve_quick_range(range, today)

    if active_preset:
        start_date = preset_start
        end_date = preset_end

    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")

    if start_date or end_date:
        export_runs = _filter_runs_by_range(all_runs, start_date, end_date)
    else:
        export_runs = runs_for_year

    export_runs = sorted(export_runs, key=lambda run: run.created_at, reverse=True)

    zero = Decimal("0")

    currency = None
    for run in export_runs:
        currency = getattr(run, "currency", None)
        if currency:
            break
    if not currency:
        if runs_for_year:
            currency = getattr(runs_for_year[0], "currency", None)
        elif all_runs:
            currency = getattr(all_runs[0], "currency", None)
    currency = currency or "USD"

    rows: list[dict[str, object]] = []
    for run in export_runs:
        card = _build_run_card(run, zero)
        frequency_display = _format_frequency_summary(card.get("frequency_counts"))
        rows.append(
            {
                "Cycle ID": card["id"],
                "Cycle": card["cycle"],
                "Created": card["created"],
                "Status": card["status"],
                "Currency": card["currency"],
                "Models Paid": card["models_paid"],
                "Total Payout": float(card["total"] or zero),
                "Paid": float(card["paid"] or zero),
                "Outstanding": float(card["outstanding"] or zero),
                "Frequency Mix": frequency_display,
            }
        )

    columns = [
        "Cycle ID",
        "Cycle",
        "Created",
        "Status",
        "Currency",
        "Models Paid",
        "Total Payout",
        "Paid",
        "Outstanding",
        "Frequency Mix",
    ]

    dataframe = pd.DataFrame(rows, columns=columns)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet_name = (
            f"Cycles_{target_year}"
            if not (start_date or end_date or active_preset)
            else "Cycles_Filtered"
        )
        dataframe.to_excel(writer, sheet_name=sheet_name, index=False)

    buffer.seek(0)

    if start_date or end_date or active_preset:
        filename_label = _format_range_label(start_date, end_date, str(target_year)).replace(" ", "_").replace("/", "-")
        filename = f"payroll_cycles_{filename_label}.xlsx"
    else:
        filename = f"payroll_cycles_{target_year}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/new")
def new_schedule_form(request: Request, user: User = Depends(get_admin_user)):
    today = date.today()
    default_month = f"{today.year:04d}-{today.month:02d}"
    return templates.TemplateResponse(
        "schedules/form.html",
        {
            "request": request,
            "user": user,
            "default_month": default_month,
            "default_currency": "USD",
            "default_output": str(DEFAULT_EXPORT_DIR),
        },
    )


@router.post("/new")
def run_schedule(
    request: Request,
    month: str = Form(...),
    currency: str = Form("USD"),
    include_inactive: str | None = Form(None),
    output_dir: str = Form(str(DEFAULT_EXPORT_DIR)),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    try:
        year_str, month_str = month.split("-")
        target_year = int(year_str)
        target_month = int(month_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Month must be in YYYY-MM format.")

    currency = currency.upper()

    export_path = Path(output_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    service = PayrollService(db)
    _, _, _, _, run_id = service.run_payroll(
        target_year=target_year,
        target_month=target_month,
        currency=currency,
        include_inactive=bool(include_inactive),
        output_dir=export_path,
    )

    return RedirectResponse(url=f"/schedules/{run_id}", status_code=303)


@router.get("/{run_id}")
def view_schedule(
    run_id: int,
    request: Request,
    code: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    status: str | None = None,
    pay_date: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    # Auto-refresh: if the run corresponds to the current month, re-run payroll
    # so newly added models for this month appear without requiring manual "Run Payroll".
    today = date.today()
    if run.target_year == today.year and run.target_month == today.month:
        # Re-run payroll for this cycle. The PayrollService will reuse the existing
        # ScheduleRun and preserve existing payout status/notes when refreshing.
        service = PayrollService(db)
        try:
            # Use the existing run's currency and export path when refreshing
            export_path = Path(run.export_path) if run.export_path else Path("exports")
            _, _, _, _, refreshed_run_id = service.run_payroll(
                target_year=run.target_year,
                target_month=run.target_month,
                currency=run.currency if getattr(run, "currency", None) else "USD",
                include_inactive=False,
                output_dir=export_path,
            )
            # If a different run record was returned, load that one instead
            if refreshed_run_id and refreshed_run_id != run.id:
                run = crud.get_schedule_run(db, refreshed_run_id)
        except Exception:
            # If refresh fails, continue to render the existing run rather than failing the page.
            # Errors are intentionally swallowed here to avoid blocking the user from viewing the run.
            pass

    run.cycle_display = format_display_date(date(run.target_year, run.target_month, 1))

    code_filter = code.strip() if code else None
    frequency_filter = frequency if frequency else None
    method_filter = payment_method if payment_method else None
    status_filter = status if status else None
    pay_date_filter: date | None = None

    if pay_date:
        pay_date_value = pay_date.strip()
        if pay_date_value:
            try:
                pay_date_filter = datetime.strptime(pay_date_value, "%m/%d/%Y").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use MM/DD/YYYY.")

    code_options = crud.payout_codes_for_run(db, run_id)
    existing_pay_dates = set(crud.payout_dates_for_run(db, run_id))

    def ordinal(day_value: int) -> str:
        if 10 <= day_value % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_value % 10, "th")
        return f"{day_value}{suffix}"

    last_day = calendar.monthrange(run.target_year, run.target_month)[1]
    candidate_days = [7, 14, 21, last_day]
    pay_date_options = []
    for day in candidate_days:
        candidate_date = date(run.target_year, run.target_month, day)
        value = format_display_date(candidate_date)
        if day == last_day:
            label = f"End of Month ({value})"
        else:
            label = f"{ordinal(day)} ({value})"
        pay_date_options.append(
            {
                "value": value,
                "label": label,
                "available": candidate_date in existing_pay_dates,
            }
        )

    payouts = crud.list_payouts_for_run(
        db,
        run_id,
        code=code_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
        status=status_filter,
        pay_date=pay_date_filter,
    )
    # Map of payout_id -> total amount deducted from cash advances (planned allocations)
    advance_allocations = crud.get_allocation_totals_for_run(db, run_id)
    payout_total = sum((payout.amount or Decimal("0")) for payout in payouts)
    validations = crud.list_validation_for_run(db, run_id)
    try:
        frequency_counts = json.loads(run.summary_frequency_counts)
    except json.JSONDecodeError:
        frequency_counts = {}

    base_filename = f"pay_schedule_{run.target_year:04d}_{run.target_month:02d}_run{run.id}"
    export_path = Path(run.export_path)

    summary = crud.run_payment_summary(db, run_id)
    status_counts = crud.payout_status_counts(db, run_id)
    method_options = crud.payment_methods_for_run(db, run_id)
    frequency_options = crud.frequencies_for_run(db, run_id)

    # Calculate overdue payments for this run
    today = date.today()
    overdue_count = 0
    overdue_amount = Decimal("0")
    for payout in payouts:
        if payout.pay_date and payout.pay_date < today and payout.status in ["not_paid", "on_hold"]:
            overdue_count += 1
            overdue_amount += payout.amount or Decimal("0")

    return templates.TemplateResponse(
        "schedules/detail.html",
        {
            "request": request,
            "user": user,
            "run": run,
            "payouts": payouts,
            "advance_allocations": advance_allocations,
            "payout_total": payout_total,
            "validations": validations,
            "frequency_counts": frequency_counts,
            "base_filename": base_filename,
            "summary": summary,
            "status_counts": status_counts,
            "overdue_count": overdue_count,
            "overdue_amount": overdue_amount,
            "today": today,
            "filters": {
                "code": code_filter or "",
                "frequency": frequency_filter or "",
                "payment_method": method_filter or "",
                "status": status_filter or "",
                "pay_date": pay_date.strip() if pay_date else "",
            },
            "status_options": PAYOUT_STATUS_ENUM,
            "payment_methods": method_options,
            "frequency_options": frequency_options,
            "code_options": code_options,
            "pay_date_options": pay_date_options,
        },
    )


@router.post("/{run_id}/delete")
def delete_schedule_run(run_id: int, db: Session = Depends(get_session), user: User = Depends(get_admin_user)):
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    crud.delete_schedule_run(db, run)
    return RedirectResponse(url="/schedules", status_code=303)


@router.get("/{run_id}/download/{file_type}")
def download_export(run_id: int, file_type: str, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    base_filename = f"pay_schedule_{run.target_year:04d}_{run.target_month:02d}_run{run.id}"
    export_dir = Path(run.export_path)

    # For schedule_csv, generate from database payouts to include status
    if file_type == "schedule_csv":
        # Build CSV from payouts in database (includes status)
        payouts = sorted(run.payouts, key=lambda p: (p.pay_date, p.code))
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Pay Date",
            "Code",
            "Working Name",
            "Method",
            "Frequency",
            "Amount",
            "Status",
            "Crypto Wallet",
            "Notes & Actions",
        ])
        
        # Write data rows
        for payout in payouts:
            model_wallet = ""
            if payout.model and getattr(payout.model, "crypto_wallet", None):
                model_wallet = payout.model.crypto_wallet

            writer.writerow([
                format_display_date(payout.pay_date),
                payout.code or "",
                payout.working_name or "",
                payout.payment_method or "",
                payout.payment_frequency.title() if payout.payment_frequency else "",
                f"{payout.amount:.2f}" if payout.amount else "",
                payout.status.replace("_", " ").title() if payout.status else "",
                model_wallet,
                payout.notes or "",
            ])
        
        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={base_filename}.csv"},
        )

    # For other file types, use the pre-generated exports
    file_mapping = {
        "xlsx": export_dir / f"{base_filename}.xlsx",
        "models_csv": export_dir / f"{base_filename}_models.csv",
        "validation_csv": export_dir / f"{base_filename}_validation.csv",
    }

    path = file_mapping.get(file_type)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Requested file not available")

    return FileResponse(path, filename=path.name)


@router.post("/{run_id}/payouts/{payout_id}/note")
def update_payout_record(
    run_id: int,
    payout_id: int,
    notes: str = Form(""),
    status: str = Form("not_paid"),
    redirect_to: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    payout = crud.get_payout(db, payout_id)
    if not payout or payout.schedule_run_id != run_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    status_value = status.strip().lower()
    if status_value not in PAYOUT_STATUS_ENUM:
        raise HTTPException(status_code=400, detail="Invalid payout status")

    trimmed = notes.strip()
    crud.update_payout(db, payout, trimmed if trimmed else None, status_value)

    target_url = redirect_to or f"/schedules/{run_id}"
    if not target_url.startswith("/schedules/"):
        target_url = f"/schedules/{run_id}"
    return RedirectResponse(url=target_url, status_code=303)


@router.post("/{run_id}/payouts/bulk-update")
def bulk_update_payouts(
    run_id: int,
    payout_ids: str = Form(""),
    status: str = Form("not_paid"),
    redirect_to: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Bulk update status for multiple payouts."""
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    status_value = status.strip().lower()
    if status_value not in PAYOUT_STATUS_ENUM:
        raise HTTPException(status_code=400, detail="Invalid payout status")

    # Parse comma-separated payout IDs
    if not payout_ids.strip():
        target_url = redirect_to or f"/schedules/{run_id}"
        if not target_url.startswith("/schedules/"):
            target_url = f"/schedules/{run_id}"
        return RedirectResponse(url=target_url, status_code=303)
    
    try:
        ids = [int(id.strip()) for id in payout_ids.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payout IDs")

    # Update each payout with new status, preserving existing notes
    for payout_id in ids:
        payout = crud.get_payout(db, payout_id)
        if payout and payout.schedule_run_id == run_id:
            # Preserve existing notes, only update status
            crud.update_payout(db, payout, payout.notes, status_value)
    
    target_url = redirect_to or f"/schedules/{run_id}"
    if not target_url.startswith("/schedules/"):
        target_url = f"/schedules/{run_id}"
    return RedirectResponse(url=target_url, status_code=303)


@router.post("/{run_id}/payouts/{payout_id}/status")
def api_update_payout_status(
    run_id: int,
    payout_id: int,
    status: str = Form(...),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """AJAX-friendly endpoint to update a single payout's status without full-page reload.

    Returns minimal JSON so the client can update the UI in-place.
    """
    payout = crud.get_payout(db, payout_id)
    if not payout or payout.schedule_run_id != run_id:
        raise HTTPException(status_code=404, detail="Payout not found")

    status_value = (status or "").strip().lower()
    if status_value not in PAYOUT_STATUS_ENUM:
        raise HTTPException(status_code=400, detail="Invalid payout status")

    # Preserve existing notes, only update status
    crud.update_payout(db, payout, payout.notes, status_value)

    # Compute overdue flag server-side to reduce client logic differences
    today = date.today()
    is_overdue = bool(payout.pay_date and payout.pay_date < today and status_value in ("not_paid", "on_hold"))

    return JSONResponse(
        {
            "ok": True,
            "payout_id": payout.id,
            "run_id": run_id,
            "new_status": status_value,
            "is_overdue": is_overdue,
        }
    )


@router.post("/{run_id}/payouts/bulk-update/status")
def api_bulk_update_payouts(
    run_id: int,
    payout_ids: str = Form(""),
    status: str = Form(...),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """AJAX-friendly endpoint to bulk update payouts without full-page reload."""
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    status_value = (status or "").strip().lower()
    if status_value not in PAYOUT_STATUS_ENUM:
        raise HTTPException(status_code=400, detail="Invalid payout status")

    if not payout_ids.strip():
        return JSONResponse({"ok": True, "updated_ids": [], "new_status": status_value})

    try:
        ids = [int(pid.strip()) for pid in payout_ids.split(",") if pid.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payout IDs")

    today = date.today()
    updated: list[int] = []
    overdue_flags: dict[int, bool] = {}

    for pid in ids:
        payout = crud.get_payout(db, pid)
        if payout and payout.schedule_run_id == run_id:
            crud.update_payout(db, payout, payout.notes, status_value)
            updated.append(pid)
            overdue_flags[pid] = bool(payout.pay_date and payout.pay_date < today and status_value in ("not_paid", "on_hold"))

    return JSONResponse({
        "ok": True,
        "updated_ids": updated,
        "new_status": status_value,
        "overdue_flags": overdue_flags,
    })

