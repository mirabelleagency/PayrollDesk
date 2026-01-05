"""Routes for managing models."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.auth import User
from app.database import get_session
from app.dependencies import templates
from app.core.config import DEFAULT_CURRENCY, DEFAULT_LOCALE
from app.core.formatting import format_display_date
from app.core.rate_limiter import limiter, EXPORT_LIMIT
from app.models import COMMISSION_PAYOUT_FREQUENCY_ENUM, FREQUENCY_ENUM, STATUS_ENUM, Payout, ScheduleRun
from app.commission import build_commission_summary, get_eligible_referrals
from app.routers.auth import get_current_user, get_admin_user
from app.schemas import AdhocPaymentCreate, AdhocPaymentUpdate, ModelCreate, ModelUpdate
from app.importers.excel_importer import ImportOptions, RunOptions, import_from_excel
import pandas as pd
import tempfile
from fastapi import Form
from openpyxl import Workbook
import os

router = APIRouter(prefix="/models", tags=["Models"])

_DECIMAL_PLACES = Decimal("0.01")
_DEFAULT_REFERRAL_DURATION_MONTHS = 12


def _normalize_filters(
    code: str | None,
    status: str | None,
    frequency: str | None,
    payment_method: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    code_filter = code.strip() if code else None
    status_filter = status.title() if status else None
    frequency_filter = frequency.lower() if frequency else None
    method_filter = payment_method.strip() if payment_method else None
    return code_filter, status_filter, frequency_filter, method_filter


def _build_model_list_context(
    request: Request,
    user: User,
    db: Session,
    code: str | None,
    status: str | None,
    frequency: str | None,
    payment_method: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code_filter, status_filter, frequency_filter, method_filter = _normalize_filters(
        code, status, frequency, payment_method
    )

    total_count = crud.count_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )

    models = crud.list_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )

    page_count = len(models)
    start_index = 1 if total_count else 0
    end_index = total_count

    # Get comprehensive payment totals (payroll + adhoc + commission) per model
    model_ids = [model.id for model in models]
    totals_map_comprehensive = crud.total_paid_by_model_comprehensive(db, model_ids)
    # For backwards compatibility, keep totals_map as combined values
    totals_map = {mid: data['combined'] for mid, data in totals_map_comprehensive.items()}
    
    total_paid_sum = crud.sum_paid_for_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )
    payment_methods = crud.list_payment_methods(db)

    status_counts_raw = crud.count_models_by_status(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )
    status_counts = {status: status_counts_raw.get(status, 0) for status in STATUS_ENUM}
    for status_value, count in status_counts_raw.items():
        if status_value not in status_counts and status_value:
            status_counts[status_value] = count

    method_counts_raw = crud.count_models_by_payment_method(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )
    method_counts: dict[str, int] = {}
    for method in payment_methods:
        method_counts[method] = method_counts_raw.get(method, 0)
    for method_value, count in method_counts_raw.items():
        if method_value not in method_counts:
            method_counts[method_value] = count

    frequency_counts_raw = crud.count_models_by_frequency(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )
    frequency_counts = {freq: frequency_counts_raw.get(freq, 0) for freq in FREQUENCY_ENUM}
    for freq_value, count in frequency_counts_raw.items():
        if freq_value not in frequency_counts and freq_value:
            frequency_counts[freq_value] = count

    # Include available schedule runs for export/filter dropdowns
    schedule_runs = crud.list_schedule_runs(db)

    export_params: dict[str, str] = {}
    if code_filter:
        export_params["code"] = code_filter
    if status_filter:
        export_params["status"] = status_filter
    if frequency_filter:
        export_params["frequency"] = frequency_filter
    if method_filter:
        export_params["payment_method"] = method_filter

    export_url = "/models/export"
    if export_params:
        export_url = f"{export_url}?{urlencode(export_params)}"

    pagination = {
        "page": 1,
        "page_size": page_count,
        "total_pages": 1,
        "total_count": total_count,
        "page_count": page_count,
        "start_index": start_index,
        "end_index": end_index,
        "has_previous": False,
        "has_next": False,
        "previous_url": None,
        "next_url": None,
        "page_links": [],
    }

    average_paid_active = Decimal("0")
    active_count = status_counts.get("Active", 0)
    if active_count:
        average_paid_active = (total_paid_sum / Decimal(active_count)).quantize(_DECIMAL_PLACES)

    context: dict[str, Any] = {
        "request": request,
        "user": user,
        "models": models,
        "schedule_runs": schedule_runs,
        "filters": {
            "code": code_filter or "",
            "status": status_filter or "",
            "frequency": frequency_filter or "",
            "payment_method": method_filter or "",
        },
        "payment_methods": payment_methods,
        "method_counts": method_counts,
        "status_options": STATUS_ENUM,
        "frequency_options": FREQUENCY_ENUM,
        "frequency_counts": frequency_counts,
        "totals_map": totals_map,
        "totals_map_comprehensive": totals_map_comprehensive,
        "total_paid_sum": total_paid_sum,
        "export_url": export_url,
        "status_counts": status_counts,
        "pagination": pagination,
        "average_paid_active": average_paid_active,
        # Currency configuration
        "app_currency": DEFAULT_CURRENCY,
        "app_locale": DEFAULT_LOCALE,
    }
    if extra:
        context.update(extra)
    context.setdefault("import_auto_runs", True)
    context.setdefault("import_update_existing", True)
    return context


def _redirect_to_model(model_id: int, **params: str) -> RedirectResponse:
    filtered = {key: value for key, value in params.items() if value}
    query = urlencode(filtered)
    url = f"/models/{model_id}"
    if query:
        url = f"{url}?{query}"
    return RedirectResponse(url=url, status_code=303)


def _parse_adjustment_rows(
    effective_dates: list[str],
    amounts: list[str],
    notes: list[str],
    baseline_date: date,
) -> list[tuple[date, Decimal, str | None]]:
    rows: dict[date, tuple[date, Decimal, str | None]] = {}

    for index, (date_value, amount_value, note_value) in enumerate(
        zip_longest(effective_dates, amounts, notes, fillvalue="")
    ):
        if not date_value and not amount_value and not note_value:
            continue
        if not date_value or not amount_value:
            raise HTTPException(status_code=400, detail=f"Adjustment row {index + 1} requires an effective date and amount.")
        try:
            effective_date = date.fromisoformat(str(date_value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid effective date for adjustment row {index + 1}.") from exc
        if effective_date < baseline_date:
            raise HTTPException(
                status_code=400,
                detail=f"Adjustment row {index + 1} must be on or after the model start date.",
            )
        try:
            amount = Decimal(str(amount_value))
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid monthly amount for adjustment row {index + 1}.") from exc
        if amount <= 0:
            raise HTTPException(status_code=400, detail=f"Adjustment row {index + 1} must use an amount greater than zero.")
        normalized_amount = amount.quantize(_DECIMAL_PLACES)
        note_text = note_value.strip() if note_value else ""
        rows[effective_date] = (effective_date, normalized_amount, note_text or None)

    adjustments = sorted(rows.values(), key=lambda item: item[0])
    return adjustments


def _parse_optional_decimal(value: str | None, field_label: str) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field_label} must be a valid number.") from exc
    if amount < 0:
        raise HTTPException(status_code=400, detail=f"{field_label} must be zero or greater.")
    return amount.quantize(_DECIMAL_PLACES)


def _parse_required_decimal(value: str | None, field_label: str) -> Decimal:
    amount = _parse_optional_decimal(value, field_label)
    if amount is None:
        raise HTTPException(status_code=400, detail=f"{field_label} is required.")
    return amount


def _parse_optional_positive_int(
    value: str | None,
    field_label: str,
    *,
    min_value: int = 1,
    max_value: int | None = None,
) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_label} must be an integer.") from exc
    if parsed < min_value:
        raise HTTPException(status_code=400, detail=f"{field_label} must be at least {min_value}.")
    if max_value is not None and parsed > max_value:
        raise HTTPException(status_code=400, detail=f"{field_label} must be {max_value} or fewer.")
    return parsed


def _normalize_commission_frequency(value: str | None, field_label: str = "Commission payout frequency") -> str:
    normalized = (value or "").strip().lower() or "dual"
    if normalized not in COMMISSION_PAYOUT_FREQUENCY_ENUM:
        allowed = ", ".join(COMMISSION_PAYOUT_FREQUENCY_ENUM)
        raise HTTPException(status_code=400, detail=f"{field_label} must be one of: {allowed}.")
    return normalized


def _checkbox_to_bool(value: str | None) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized not in ("", "0", "false", "off")


def _resolve_referrer_id(
    db: Session,
    raw_value: str | None,
    *,
    current_model_id: int | None = None,
) -> int | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    if not normalized:
        return None
    try:
        referrer_id = int(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Selected referrer is invalid.") from exc
    referrer = crud.get_model(db, referrer_id)
    if not referrer:
        raise HTTPException(status_code=400, detail="Selected referrer does not exist.")
    if current_model_id is not None and referrer_id == current_model_id:
        raise HTTPException(status_code=400, detail="A model cannot refer itself.")
    return referrer_id


def _referrable_model_options(db: Session, exclude_model_id: int | None = None) -> list[dict[str, str | int]]:
    options: list[dict[str, str | int]] = []
    for candidate in crud.list_models(db):
        if exclude_model_id and candidate.id == exclude_model_id:
            continue
        label = f"{candidate.working_name or candidate.code} ({candidate.code})"
        options.append({
            "id": candidate.id,
            "label": label,
            "status": candidate.status,
        })
    options.sort(key=lambda item: str(item["label"]).lower())
    return options


def _parse_referral_term_rows(
    model,
    referral_ids: list[str],
    amounts: list[str],
    frequencies: list[str],
    durations: list[str],
    actives: list[str],
) -> list[crud.ReferralTermPayload]:
    if not referral_ids or not getattr(model, "referrals", None):
        return []

    referral_lookup = {referral.id: referral for referral in model.referrals if referral.id}
    payloads: list[crud.ReferralTermPayload] = []

    for index, raw_id in enumerate(referral_ids):
        normalized_id = (raw_id or "").strip()
        if not normalized_id:
            continue
        try:
            referral_id = int(normalized_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid referral identifier in referral program section.") from exc
        referral = referral_lookup.get(referral_id)
        if not referral:
            continue

        amount_label = f"Commission amount for {referral.working_name or referral.code or 'referral'}"
        amount_value = amounts[index] if index < len(amounts) else None
        frequency_value = frequencies[index] if index < len(frequencies) else None
        duration_value = durations[index] if index < len(durations) else None
        active_value = actives[index] if index < len(actives) else "1"

        amount = _parse_required_decimal(amount_value, amount_label)
        frequency = _normalize_commission_frequency(frequency_value, f"Payout frequency for {referral.working_name or referral.code or 'referral'}")
        duration = _parse_optional_positive_int(
            duration_value,
            f"Commission duration for {referral.working_name or referral.code or 'referral'}",
            min_value=1,
            max_value=36,
        )
        is_active = _checkbox_to_bool(active_value)

        payloads.append(
            crud.ReferralTermPayload(
                referral_model_id=referral_id,
                commission_per_referral=amount,
                commission_payout_frequency=frequency,
                commission_duration_months=duration,
                is_active=is_active,
            )
        )

    return payloads


@router.get("/")
def list_models(
    request: Request,
    code: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    context = _build_model_list_context(
        request,
        user,
        db,
        code,
        status,
        frequency,
        payment_method,
    )
    return templates.TemplateResponse(request, "models/list.html", context)


@router.get("/payments")
def list_all_model_payments(
    request: Request,
    code: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    payment_status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Render the consolidated payment view across all models."""

    code_filter, status_filter, frequency_filter, method_filter = _normalize_filters(
        code, status, frequency, payment_method
    )

    models = crud.list_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )

    all_payments: list[dict[str, Any]] = []
    zero = Decimal("0")
    
    # Parse date filters
    start_date_obj = None
    end_date_obj = None
    if start_date:
        try:
            start_date_obj = date.fromisoformat(start_date)
        except (ValueError, TypeError):
            pass
    if end_date:
        try:
            end_date_obj = date.fromisoformat(end_date)
        except (ValueError, TypeError):
            pass

    for model in models:
        payouts = crud.list_payouts_for_model(db, model.id)
        for payout in payouts:
            if payment_status and payout.status != payment_status:
                continue
            
            # Apply date range filter
            if start_date_obj and payout.pay_date and payout.pay_date < start_date_obj:
                continue
            if end_date_obj and payout.pay_date and payout.pay_date > end_date_obj:
                continue

            run = crud.get_schedule_run(db, payout.schedule_run_id) if payout.schedule_run_id else None

            all_payments.append(
                {
                    "payout": payout,
                    "model": model,
                    "run": run,
                }
            )

    all_payments.sort(key=lambda item: item["payout"].pay_date or date.min, reverse=True)

    total_amount = sum((payment["payout"].amount or zero) for payment in all_payments)
    paid_amount = sum(
        (payment["payout"].amount or zero)
        for payment in all_payments
        if payment["payout"].status == "paid"
    )
    unpaid_amount = sum(
        (payment["payout"].amount or zero)
        for payment in all_payments
        if payment["payout"].status in {"not_paid", "on_hold"}
    )

    status_counts: dict[str, int] = {}
    frequency_counts: dict[str, int] = {}
    method_counts: dict[str, int] = {}

    for payment in all_payments:
        status_value = payment["payout"].status
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

        frequency_value = payment["payout"].payment_frequency
        if frequency_value:
            frequency_counts[frequency_value] = frequency_counts.get(frequency_value, 0) + 1

        method_value = payment["payout"].payment_method
        if method_value:
            method_counts[method_value] = method_counts.get(method_value, 0) + 1

    payment_methods = sorted(
        set(model.payment_method for model in crud.list_models(db) if model.payment_method)
    )

    return templates.TemplateResponse(
        request,
        "models/payments.html",
        {
            "request": request,
            "user": user,
            "all_payments": all_payments,
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "unpaid_amount": unpaid_amount,
            "status_counts": status_counts,
            "frequency_counts": frequency_counts,
            "method_counts": method_counts,
            "models": models,
            "payment_methods": payment_methods,
            "frequency_options": list(FREQUENCY_ENUM),
            "status_options": list(STATUS_ENUM),
            "payment_status_options": ["paid", "not_paid", "on_hold"],
            "filters": {
                "code": code_filter or "",
                "status": status_filter or "",
                "frequency": frequency_filter or "",
                "payment_method": method_filter or "",
                "payment_status": payment_status or "",
                "start_date": start_date or "",
                "end_date": end_date or "",
            },
        },
    )


@router.get("/snapshot")
def snapshot_models(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    models = crud.list_models(db)
    sorted_models = sorted(models, key=lambda item: ((item.working_name or "").lower(), item.code))
    return templates.TemplateResponse(
        request,
        "models/snapshot.html",
        {
            "request": request,
            "user": user,
            "models": sorted_models,
        },
    )


@router.get("/export")
def export_models_csv(
    code: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    include_payments: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Export models to CSV.
    If include_payments=true, includes payment history (paid payouts) for each model.
    """
    code_filter, status_filter, frequency_filter, method_filter = _normalize_filters(
        code, status, frequency, payment_method
    )

    models = crud.list_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )

    totals_map = crud.total_paid_by_model(db, [model.id for model in models])
    
    # Check if user wants to include payment history
    include_payment_history = include_payments and include_payments.lower() == "true"

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # Header row - always include payment columns to match /schedules/ view
    writer.writerow(
        [
            "Code",
            "Status",
            "Real Name",
            "Working Name",
            "Start Date",
            "Payment Method",
            "Payment Frequency",
            "Monthly Amount",
            "Crypto Wallet",
            "Pay Date",
            "Amount",
            "Status (Payment)",
            "Notes",
        ]
    )

    for model in models:
        start_date_value = format_display_date(model.start_date)

        # Get paid payouts for this model
        paid_payouts = crud.get_paid_payouts_for_model(db, model.id)
        
        if paid_payouts:
            # Write one row per payment
            for payout in paid_payouts:
                pay_date_value = format_display_date(payout.pay_date)
                writer.writerow(
                    [
                        model.code,
                        model.status,
                        model.real_name,
                        model.working_name,
                        start_date_value,
                        model.payment_method,
                        model.payment_frequency,
                        f"{model.amount_monthly:.2f}",
                        model.crypto_wallet or "",
                        pay_date_value,
                        f"{payout.amount:.2f}",
                        payout.status,
                        payout.notes or "",
                    ]
                )
        else:
            # Write model row with empty payment fields if no payouts
            writer.writerow(
                [
                    model.code,
                    model.status,
                    model.real_name,
                    model.working_name,
                    start_date_value,
                    model.payment_method,
                    model.payment_frequency,
                    f"{model.amount_monthly:.2f}",
                    model.crypto_wallet or "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    buffer.seek(0)
    filename_parts = ["models_export"]
    if code_filter:
        filename_parts.append(code_filter.replace(" ", "_"))
    if include_payment_history:
        filename_parts.append("with_payments")
    filename = "_".join(filename_parts) + ".csv"

    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
    }

    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/{model_id}/payments.json")
def model_payments_json(
    model_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get paginated payment history for a model.
    
    Args:
        model_id: The model ID
        page: Page number (1-indexed, default 1)
        per_page: Items per page (default 20, max 100)
    """
    # Validate pagination params
    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Get total count first
    all_payouts = crud.list_payouts_for_model(db, model_id)
    total_count = len(all_payouts)
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    
    # Calculate offset and slice payouts for current page
    offset = (page - 1) * per_page
    payouts = all_payouts[offset:offset + per_page]

    run_ids = {payout.schedule_run_id for payout in payouts if payout.schedule_run_id}
    runs_map: dict[int, ScheduleRun] = {}
    if run_ids:
        runs = db.execute(select(ScheduleRun).where(ScheduleRun.id.in_(run_ids))).scalars().all()
        runs_map = {run.id: run for run in runs}

    # Calculate totals from ALL payouts (not just current page)
    total_paid = Decimal("0")
    latest_pay_date: date | None = None
    for payout in all_payouts:
        if payout.status == "paid":
            total_paid += Decimal(payout.amount or 0)
        pay_date = payout.pay_date
        if pay_date and (latest_pay_date is None or pay_date > latest_pay_date):
            latest_pay_date = pay_date

    # Build rows for current page
    payout_rows: list[dict[str, Any]] = []
    for payout in payouts:
        amount = Decimal(payout.amount or 0)
        pay_date = payout.pay_date

        run = runs_map.get(payout.schedule_run_id) if payout.schedule_run_id else None
        run_payload = None
        if run:
            run_payload = {
                "id": run.id,
                "target_year": run.target_year,
                "target_month": run.target_month,
                "label": f"{run.target_year}-{run.target_month:02d}",
            }

        payout_rows.append(
            {
                "id": payout.id,
                "pay_date": pay_date.isoformat() if pay_date else None,
                "pay_date_display": format_display_date(pay_date) if pay_date else None,
                "amount": str(amount),
                "amount_value": float(amount),
                "payment_method": payout.payment_method,
                "payment_frequency": payout.payment_frequency,
                "status": payout.status,
                "notes": payout.notes or "",
                "run": run_payload,
            }
        )

    summary = {
        "count": total_count,
        "total_paid": str(total_paid),
        "total_paid_value": float(total_paid),
        "latest_pay_date": latest_pay_date.isoformat() if latest_pay_date else None,
        "latest_pay_date_display": format_display_date(latest_pay_date) if latest_pay_date else None,
    }
    
    pagination = {
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }

    return JSONResponse(  # type: ignore[arg-type]
        content={
            "model": {
                "id": model.id,
                "code": model.code,
                "working_name": model.working_name,
            },
            "payouts": payout_rows,
            "summary": summary,
            "pagination": pagination,
        }
    )


@router.get("/new")
def new_model_form(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    return templates.TemplateResponse(
        request,
        "models/form.html",
        {
            "request": request,
            "user": user,
            "action": "create",
            "referrable_models": _referrable_model_options(db),
            "commission_frequency_options": COMMISSION_PAYOUT_FREQUENCY_ENUM,
            "referral_terms": {},
        },
    )


@router.post("/new")
def create_model(
    request: Request,
    status: str = Form(...),
    code: str = Form(...),
    real_name: str = Form(...),
    working_name: str = Form(...),
    start_date: date = Form(...),
    payment_method: str = Form(...),
    payment_frequency: str = Form(...),
    amount_monthly: Decimal = Form(...),
    crypto_wallet: str | None = Form(None),
    referred_by_model_id: str | None = Form(None),
    commission_active: str | None = Form(None),
    commission_per_referral: str | None = Form(None),
    commission_payout_frequency: str = Form("dual"),
    commission_duration_months: str | None = Form(None),
    adjustment_effective_dates: list[str] = Form([]),
    adjustment_amounts: list[str] = Form([]),
    adjustment_notes: list[str] = Form([]),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    commission_enabled = _checkbox_to_bool(commission_active)
    commission_amount = _parse_optional_decimal(commission_per_referral, "Commission per referral")
    commission_duration = _parse_optional_positive_int(
        commission_duration_months,
        "Commission duration",
        min_value=1,
        max_value=36,
    )
    referrer_id = _resolve_referrer_id(db, referred_by_model_id)

    if referrer_id is not None:
        if commission_duration is None:
            commission_duration = _DEFAULT_REFERRAL_DURATION_MONTHS
        commission_status = "unpaid"
    else:
        commission_duration = None
        commission_status = "unpaid"

    if referrer_id is not None:
        commission_enabled = False
        commission_amount = None
        commission_payout_frequency = "dual"

    payload = ModelCreate(
        status=status,
        code=code,
        real_name=real_name,
        working_name=working_name,
        start_date=start_date,
        payment_method=payment_method,
        payment_frequency=payment_frequency,
        amount_monthly=amount_monthly,
        crypto_wallet=crypto_wallet if crypto_wallet else None,
        referred_by_model_id=referrer_id,
        commission_active=commission_enabled,
        commission_per_referral=commission_amount,
        commission_payout_frequency=commission_payout_frequency,
        commission_duration_months=commission_duration,
        commission_status=commission_status,
    )
    if crud.get_model_by_code(db, payload.code):
        raise HTTPException(status_code=400, detail="Model code already exists.")
    model = crud.create_model(db, payload)

    adjustments = _parse_adjustment_rows(
        adjustment_effective_dates,
        adjustment_amounts,
        adjustment_notes,
        payload.start_date,
    )
    if adjustments:
        for effective_date, amount, note_text in adjustments:
            crud.create_compensation_adjustment(db, model, effective_date, amount, note_text)
        db.commit()
    return RedirectResponse(url="/models", status_code=303)


@router.get("/{model_id}")
def view_model(model_id: int, request: Request, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """View model details in read-only mode."""
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get comprehensive payment totals for this model (payroll + adhoc + commission)
    totals_comprehensive = crud.total_paid_by_model_comprehensive(db, [model.id])
    model_totals = totals_comprehensive.get(model.id, {
        'payroll': Decimal("0"),
        'adhoc': Decimal("0"),
        'commission': Decimal("0"),
        'combined': Decimal("0"),
    })
    total_paid = model_totals['combined']
    payroll_total = model_totals['payroll']
    adhoc_total = model_totals['adhoc']
    commission_total = model_totals['commission']
    
    # Get paid payouts (unified source of truth for payment history)
    paid_payouts = crud.get_paid_payouts_for_model(db, model_id)
    adhoc_payments = crud.list_adhoc_payments(db, model_id)
    error_message = request.query_params.get("error")
    success_message = request.query_params.get("success")
    
    # Cash advances context
    advances = crud.list_advances_for_model(db, model.id)
    advances_outstanding = crud.outstanding_advance_total(db, model.id)

    # Commission snapshot (kept independent from payroll runs)
    commission_summary = build_commission_summary(db, model)
    commission_referrals = get_eligible_referrals(db, model)
    referrer_model = model.referred_by
    referral_terms_map = {term.referral_model_id: term for term in crud.list_referral_terms(db, model.id)}
    
    # Commission payouts with status tracking
    from app.models import CommissionPayout
    commission_payouts = db.query(CommissionPayout).filter(
        (CommissionPayout.referrer_model_id == model.id) | (CommissionPayout.referral_model_id == model.id)
    ).order_by(CommissionPayout.pay_date.desc()).all()

    return templates.TemplateResponse(
        request,
        "models/view.html",
        {
            "request": request,
            "user": user,
            "model": model,
            "total_paid": total_paid,
            "payroll_total": payroll_total,
            "adhoc_total": adhoc_total,
            "commission_total": commission_total,
            "paid_payouts": paid_payouts,
            "adhoc_payments": adhoc_payments,
            "advances": advances,
            "advances_outstanding": advances_outstanding,
            "commission_summary": commission_summary,
            "commission_referrals": commission_referrals,
            "referrer_model": referrer_model,
            "referral_terms_map": referral_terms_map,
            "commission_payouts": commission_payouts,
            "error_message": error_message,
            "success_message": success_message,
        },
    )


@router.get("/{model_id}/snapshot.json")
def model_snapshot_data(
    model_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    adjustments = sorted(list(model.compensation_adjustments or []), key=lambda adj: adj.effective_date)
    total_paid_map = crud.total_paid_by_model(db, [model.id])
    total_paid = total_paid_map.get(model.id)
    adhoc_payments = crud.list_adhoc_payments(db, model_id)
    pending_adhoc = [payment for payment in adhoc_payments if payment.status == "pending"]
    payload = {
        "model": {
            "id": model.id,
            "code": model.code,
            "status": model.status,
            "real_name": model.real_name,
            "working_name": model.working_name,
            "start_date": model.start_date.isoformat() if model.start_date else None,
            "start_date_display": format_display_date(model.start_date) or None,
            "payment_method": model.payment_method,
            "payment_frequency": model.payment_frequency,
            "amount_monthly": str(model.amount_monthly),
            "crypto_wallet": model.crypto_wallet,
        },
        "adjustments": [
            {
                "id": adjustment.id,
                "effective_date": adjustment.effective_date.isoformat(),
                "effective_date_display": format_display_date(adjustment.effective_date) or None,
                "amount_monthly": str(adjustment.amount_monthly),
                "notes": adjustment.notes,
            }
            for adjustment in adjustments
        ],
        "stats": {
            "total_paid": str(total_paid) if total_paid is not None else None,
            "adhoc_pending_count": len(pending_adhoc),
            "adhoc_total_count": len(adhoc_payments),
        },
    }
    return JSONResponse(content=payload)


@router.post("/{model_id}/adhoc-payments")
def create_adhoc_payment(
    model_id: int,
    pay_date: str = Form(...),
    amount: str = Form(...),
    description: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    pay_date_value = (pay_date or "").strip()
    if not pay_date_value:
        return _redirect_to_model(model_id, error="Pay date is required.")
    try:
        pay_date_obj = date.fromisoformat(pay_date_value)
    except ValueError:
        return _redirect_to_model(model_id, error="Pay date must use YYYY-MM-DD format.")

    amount_value = (amount or "").strip()
    if not amount_value:
        return _redirect_to_model(model_id, error="Amount is required.")
    try:
        amount_decimal = Decimal(amount_value)
    except (InvalidOperation, ValueError):
        return _redirect_to_model(model_id, error="Amount must be a valid number.")
    if amount_decimal <= 0:
        return _redirect_to_model(model_id, error="Amount must be greater than zero.")
    amount_decimal = amount_decimal.quantize(_DECIMAL_PLACES)

    payload = AdhocPaymentCreate(
        pay_date=pay_date_obj,
        amount=amount_decimal,
        description=description.strip() if description else None,
        notes=notes.strip() if notes else None,
    )
    crud.create_adhoc_payment(db, model, payload)
    return _redirect_to_model(model_id, success="Ad hoc payment created.")


@router.post("/{model_id}/adhoc-payments/{payment_id}/status")
def update_adhoc_payment_status(
    model_id: int,
    payment_id: int,
    action: str = Form(...),
    return_url: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    payment = crud.get_adhoc_payment(db, payment_id)
    if not payment or payment.model_id != model_id:
        raise HTTPException(status_code=404, detail="Ad hoc payment not found")

    action_map = {
        "mark_paid": ("paid", "Ad hoc payment marked as paid."),
        "mark_pending": ("pending", "Ad hoc payment set to pending."),
        "cancel": ("cancelled", "Ad hoc payment cancelled."),
    }

    target = action_map.get(action)
    if not target:
        raise HTTPException(status_code=400, detail="Unsupported action")

    status, message = target
    crud.set_adhoc_payment_status(db, payment, status)
    if return_url:
        return RedirectResponse(url=return_url, status_code=303)
    return _redirect_to_model(model_id, success=message)


@router.post("/{model_id}/adhoc-payments/{payment_id}/notes")
def update_adhoc_payment_notes(
    model_id: int,
    payment_id: int,
    notes: str = Form(""),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    payment = crud.get_adhoc_payment(db, payment_id)
    if not payment or payment.model_id != model_id:
        raise HTTPException(status_code=404, detail="Ad hoc payment not found")

    update_payload = AdhocPaymentUpdate(description=None, notes=notes.strip() if notes else None)
    crud.update_adhoc_payment(db, payment, update_payload)
    return _redirect_to_model(model_id, success="Notes updated.")


@router.post("/{model_id}/adhoc-payments/{payment_id}/delete")
def delete_adhoc_payment(
    model_id: int,
    payment_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    payment = crud.get_adhoc_payment(db, payment_id)
    if not payment or payment.model_id != model_id:
        raise HTTPException(status_code=404, detail="Ad hoc payment not found")

    crud.delete_adhoc_payment(db, payment)
    return _redirect_to_model(model_id, success="Ad hoc payment deleted.")


@router.get("/{model_id}/edit")
def edit_model_form(model_id: int, request: Request, db: Session = Depends(get_session), user: User = Depends(get_admin_user)):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    referral_terms = {term.referral_model_id: term for term in crud.list_referral_terms(db, model.id)}
    return templates.TemplateResponse(
        request,
        "models/form.html",
        {
            "request": request,
            "user": user,
            "action": "edit",
            "model": model,
            "referrable_models": _referrable_model_options(db, exclude_model_id=model.id),
            "commission_frequency_options": COMMISSION_PAYOUT_FREQUENCY_ENUM,
            "referral_terms": referral_terms,
        },
    )


@router.post("/export")
@limiter.limit(EXPORT_LIMIT)
def export_models_data(
    request: Request,
    include: list[str] | None = Form(None),
    run_id: str | None = Form(None),
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Export selected datasets across models to an Excel workbook.

    Form fields:
    - include[]: list of dataset keys
    - run_id, start_date, end_date: optional filters applied where relevant
    
    Rate limited to 5 requests per minute to prevent abuse.
    """
    # Parse run_id from form: browser submits empty string when the "All runs" option is selected.
    parsed_run_id: int | None = None
    if run_id:
        try:
            parsed_run_id = int(run_id)
        except ValueError:
            # If parsing fails, treat as no run filter rather than raising a 422
            parsed_run_id = None

    selection = set(include or ['models'])

    sheets: dict[str, pd.DataFrame] = {}

    # Models sheet
    if 'models' in selection:
        models = crud.list_models(db)
        rows = []
        for m in models:
            rows.append({
                'id': m.id,
                'code': m.code,
                'working_name': m.working_name,
                'real_name': m.real_name,
                'status': m.status,
                'payment_method': m.payment_method,
                'payment_frequency': m.payment_frequency,
                'amount_monthly': float(m.amount_monthly or 0),
                'start_date': m.start_date.isoformat() if m.start_date else None,
            })
        sheets['Models'] = pd.DataFrame(rows)

    # Runs sheet
    if 'runs' in selection:
        runs = crud.list_schedule_runs(db)
        rows = []
        for r in runs:
            rows.append({
                'id': r.id,
                'target_year': r.target_year,
                'target_month': r.target_month,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'currency': r.currency,
            })
        sheets['Schedule Runs'] = pd.DataFrame(rows)

    # Payouts across models (apply run/date filters)
    if 'payouts' in selection:
        rows = []
        # iterate all models' payouts
        all_models = crud.list_models(db)
        for m in all_models:
            payouts = crud.list_payouts_for_model(db, m.id)
            for p in payouts:
                if parsed_run_id and p.schedule_run_id != parsed_run_id:
                    continue
                if start_date and p.pay_date and p.pay_date < date.fromisoformat(start_date):
                    continue
                if end_date and p.pay_date and p.pay_date > date.fromisoformat(end_date):
                    continue
                rows.append({
                    'model_id': m.id,
                    'model_code': m.code,
                    'payout_id': p.id,
                    'pay_date': p.pay_date.isoformat() if p.pay_date else None,
                    'amount': float(p.amount or 0),
                    'status': p.status,
                    'notes': p.notes,
                    'run_id': p.schedule_run_id,
                })
        sheets['Payouts'] = pd.DataFrame(rows)

    # Adhoc payments
    if 'adhoc' in selection:
        rows = []
        all_models = crud.list_models(db)
        for m in all_models:
            for a in crud.list_adhoc_payments(db, m.id):
                rows.append({
                    'model_id': m.id,
                    'model_code': m.code,
                    'id': a.id,
                    'pay_date': a.pay_date.isoformat() if a.pay_date else None,
                    'amount': float(a.amount or 0),
                    'status': a.status,
                    'description': a.description,
                    'notes': a.notes,
                })
        sheets['Adhoc Payments'] = pd.DataFrame(rows)

    # Adjustments
    if 'adjustments' in selection:
        rows = []
        for m in crud.list_models(db):
            for adj in sorted(list(m.compensation_adjustments or []), key=lambda a: a.effective_date):
                rows.append({
                    'model_id': m.id,
                    'model_code': m.code,
                    'id': adj.id,
                    'effective_date': adj.effective_date.isoformat(),
                    'amount_monthly': float(adj.amount_monthly),
                    'notes': adj.notes,
                })
        sheets['Adjustments'] = pd.DataFrame(rows)

    # Advances + repayments
    if 'advances' in selection:
        rows = []
        for m in crud.list_models(db):
            for adv in crud.list_advances_for_model(db, m.id):
                rows.append({
                    'model_id': m.id,
                    'model_code': m.code,
                    'advance_id': adv.id,
                    'created_at': adv.created_at.isoformat() if adv.created_at else None,
                    'status': adv.status,
                    'amount_total': float(adv.amount_total or 0),
                    'amount_remaining': float(adv.amount_remaining or 0),
                    'strategy': adv.strategy,
                    'notes': adv.notes,
                })
        sheets['Advances'] = pd.DataFrame(rows)

    # Build Excel in-memory
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                pd.DataFrame([{'note': 'no data'}]).to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    filename = "models_export.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)


@router.post("/{model_id}/edit")
def update_model(
    model_id: int,
    request: Request,
    status: str = Form(...),
    code: str = Form(...),
    real_name: str = Form(...),
    working_name: str = Form(...),
    start_date: date = Form(...),
    payment_method: str = Form(...),
    payment_frequency: str = Form(...),
    amount_monthly: Decimal = Form(...),
    crypto_wallet: str | None = Form(None),
    referred_by_model_id: str | None = Form(None),
    commission_active: str | None = Form(None),
    commission_per_referral: str | None = Form(None),
    commission_payout_frequency: str = Form("dual"),
    commission_duration_months: str | None = Form(None),
    adjustment_effective_dates: list[str] = Form([]),
    adjustment_amounts: list[str] = Form([]),
    adjustment_notes: list[str] = Form([]),
    referral_term_referral_ids: list[str] = Form([]),
    referral_term_amounts: list[str] = Form([]),
    referral_term_frequencies: list[str] = Form([]),
    referral_term_durations: list[str] = Form([]),
    referral_term_actives: list[str] = Form([]),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    commission_enabled = _checkbox_to_bool(commission_active)
    commission_amount = _parse_optional_decimal(commission_per_referral, "Commission per referral")
    commission_duration = _parse_optional_positive_int(
        commission_duration_months,
        "Commission duration",
        min_value=1,
        max_value=36,
    )
    previous_referrer_id = model.referred_by_model_id
    referrer_id = _resolve_referrer_id(db, referred_by_model_id, current_model_id=model.id)

    if previous_referrer_id and previous_referrer_id != referrer_id:
        crud.delete_referral_term_for_referral(db, model.id)

    commission_status_value = (model.commission_status or "unpaid").strip().lower()
    if referrer_id is not None:
        if commission_duration is None:
            commission_duration = model.commission_duration_months or _DEFAULT_REFERRAL_DURATION_MONTHS
        if previous_referrer_id != referrer_id:
            commission_status_value = "unpaid"
    else:
        commission_duration = None
        commission_status_value = "unpaid"

    if referrer_id is not None:
        commission_enabled = False
        commission_amount = None
        commission_payout_frequency = "dual"

    referral_term_payloads: list[crud.ReferralTermPayload] = _parse_referral_term_rows(
        model,
        referral_term_referral_ids,
        referral_term_amounts,
        referral_term_frequencies,
        referral_term_durations,
        referral_term_actives,
    )
    if referral_term_payloads:
        commission_enabled = any(term.is_active for term in referral_term_payloads)

    payload = ModelUpdate(
        status=status,
        code=code,
        real_name=real_name,
        working_name=working_name,
        start_date=start_date,
        payment_method=payment_method,
        payment_frequency=payment_frequency,
        amount_monthly=amount_monthly,
        crypto_wallet=crypto_wallet if crypto_wallet else None,
        referred_by_model_id=referrer_id,
        commission_active=commission_enabled,
        commission_per_referral=commission_amount,
        commission_payout_frequency=commission_payout_frequency,
        commission_duration_months=commission_duration,
        commission_status=commission_status_value,
    )

    existing = crud.get_model_by_code(db, payload.code)
    if existing and existing.id != model.id:
        raise HTTPException(status_code=400, detail="Another model already uses this code.")

    updated_model = crud.update_model(db, model, payload)

    adjustments = _parse_adjustment_rows(
        adjustment_effective_dates,
        adjustment_amounts,
        adjustment_notes,
        payload.start_date,
    )

    existing_by_date = {adj.effective_date: adj for adj in updated_model.compensation_adjustments}

    if adjustments:
        keep_dates: set[date] = set()
        for effective_date, amount, note_text in adjustments:
            crud.create_compensation_adjustment(db, updated_model, effective_date, amount, note_text)
            keep_dates.add(effective_date)
        for effective_date, adjustment in existing_by_date.items():
            if effective_date not in keep_dates and effective_date > payload.start_date:
                db.delete(adjustment)
        db.commit()

    if updated_model.referrals:
        crud.upsert_referral_terms(db, updated_model, referral_term_payloads)
        db.commit()
    elif updated_model.referral_terms:
        crud.upsert_referral_terms(db, updated_model, [])
        db.commit()

    return RedirectResponse(url=f"/models/{model_id}/edit?saved=1", status_code=303)


# --- Cash Advances routes ---------------------------------------------------

@router.post("/{model_id}/advances")
def create_model_advance(
    model_id: int,
    amount_total: str = Form(...),
    strategy: str = Form("fixed"),
    fixed_amount: str = Form(""),
    percent_rate: str = Form(""),
    notes: str = Form(""),
    auto_approve: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    def _to_decimal(value: str | None) -> Decimal | None:
        if not value:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    amount = _to_decimal(amount_total)
    if not amount or amount <= 0:
        return _redirect_to_model(model_id, error="Advance amount must be greater than zero.")

    fx_amt = _to_decimal(fixed_amount)
    pct = _to_decimal(percent_rate)
    try:
        adv = crud.create_advance(
            db,
            model,
            amount_total=amount.quantize(Decimal("0.01")),
            strategy=strategy,
            fixed_amount=(fx_amt.quantize(Decimal("0.01")) if fx_amt is not None else None),
            percent_rate=(pct.quantize(Decimal("0.01")) if pct is not None else None),
            notes=(notes.strip() if notes else None),
        )
        if auto_approve is not None:
            crud.approve_advance(db, adv, activate=True)
        return _redirect_to_model(model_id, success="Advance request submitted" + (" and activated" if auto_approve else "."))
    except Exception as exc:
        return _redirect_to_model(model_id, error=str(exc))


@router.post("/{model_id}/advances/{advance_id}/delete")
def delete_model_advance(
    model_id: int,
    advance_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    adv = crud.get_advance(db, advance_id)
    if not adv or adv.model_id != model_id:
        raise HTTPException(status_code=404, detail="Advance not found")
    try:
        crud.delete_advance(db, adv)
        return _redirect_to_model(model_id, success="Advance deleted.")
    except Exception as exc:
        return _redirect_to_model(model_id, error=str(exc))


@router.post("/{model_id}/advances/{advance_id}/approve")
def approve_model_advance(
    model_id: int,
    advance_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    adv = crud.get_advance(db, advance_id)
    if not adv or adv.model_id != model_id:
        raise HTTPException(status_code=404, detail="Advance not found")
    try:
        crud.approve_advance(db, adv, activate=True)
        return _redirect_to_model(model_id, success="Advance approved and activated.")
    except Exception as exc:
        return _redirect_to_model(model_id, error=str(exc))


@router.post("/{model_id}/advances/{advance_id}/repay")
def repay_model_advance(
    model_id: int,
    advance_id: int,
    amount: str = Form(...),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    adv = crud.get_advance(db, advance_id)
    if not adv or adv.model_id != model_id:
        raise HTTPException(status_code=404, detail="Advance not found")
    try:
        amt = Decimal(str(amount))
        crud.record_advance_repayment(db, adv, amount=amt, source="manual")
        db.refresh(adv)
        return _redirect_to_model(model_id, success="Repayment recorded.")
    except Exception as exc:
        return _redirect_to_model(model_id, error=str(exc))


@router.post("/{model_id}/advances/{advance_id}/note")
def update_advance_note(
    model_id: int,
    advance_id: int,
    notes: str = Form(""),
    redirect_to: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    adv = crud.get_advance(db, advance_id)
    if not adv or adv.model_id != model_id:
        raise HTTPException(status_code=404, detail="Advance not found")
    try:
        adv.notes = notes.strip() if notes and notes.strip() else None
        db.add(adv)
        db.commit()
        target = redirect_to or f"/models/{model_id}"
        if not target.startswith("/models/"):
            target = f"/models/{model_id}"
        return RedirectResponse(url=target, status_code=303)
    except Exception as exc:
        return _redirect_to_model(model_id, error=str(exc))



@router.post("/{model_id}/delete")
def delete_model(model_id: int, db: Session = Depends(get_session), user: User = Depends(get_admin_user)):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    crud.delete_model(db, model)
    return RedirectResponse(url="/models", status_code=303)


@router.post("/import")
async def import_models_excel(
    request: Request,
    excel_file: UploadFile = File(...),
    target_month: str | None = Form(None),
    schedule_run_id: str | None = Form(None),
    currency: str = Form("USD"),
    export_dir: str = Form("exports"),
    update_existing: str | None = Form(None),
    model_sheet: str = Form("Models"),
    payout_sheet: str = Form("Payouts"),
    auto_runs: str | None = Form(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    extra_context: dict[str, Any] = {}
    try:
        contents = await excel_file.read()
        if not contents:
            raise ValueError("The uploaded file is empty.")
        filename = (excel_file.filename or "").lower()
        if not filename.endswith((".xlsx", ".xlsm", ".xls")):
            raise ValueError("Upload an Excel file with the .xlsx extension.")

        auto_generate_runs = auto_runs is not None
        extra_context["import_auto_runs"] = auto_generate_runs
        extra_context["import_update_existing"] = update_existing is not None

        run_id: int | None = None
        create_schedule_run = False
        target_year_int: int | None = None
        target_month_int: int | None = None

        if auto_generate_runs:
            create_schedule_run = True
        else:
            if schedule_run_id:
                try:
                    run_id = int(schedule_run_id)
                except ValueError as exc:
                    raise ValueError("Schedule run id must be a number.") from exc

            create_schedule_run = run_id is None
            if create_schedule_run:
                if not target_month:
                    raise ValueError("Select a target month to create a schedule run.")
                try:
                    year_str, month_str = target_month.split("-")
                    target_year_int = int(year_str)
                    target_month_int = int(month_str)
                except ValueError as exc:
                    raise ValueError("Target month must be in YYYY-MM format.") from exc

        import_options = ImportOptions(
            model_sheet=model_sheet or "Models",
            payout_sheet=payout_sheet or "Payouts",
            update_existing=update_existing is not None,
        )
        run_options = RunOptions(
            schedule_run_id=run_id,
            create_schedule_run=create_schedule_run,
            target_year=target_year_int,
            target_month=target_month_int,
            currency=(currency or "USD").strip() or "USD",
            export_dir=(export_dir or "exports").strip() or "exports",
            auto_generate_runs=auto_generate_runs,
        )

        summary = import_from_excel(db, contents, import_options, run_options)
        db.commit()
        db.expire_all()
        extra_context["import_summary"] = summary
    except Exception as exc:
        db.rollback()
        extra_context["import_error"] = str(exc)

    context = _build_model_list_context(
        request,
        user,
        db,
        None,
        None,
        None,
        None,
        extra=extra_context,
    )
    return templates.TemplateResponse(request, "models/list.html", context)

