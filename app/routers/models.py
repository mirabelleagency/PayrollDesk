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
from app.core.formatting import format_display_date
from app.models import FREQUENCY_ENUM, STATUS_ENUM, Payout, ScheduleRun
from app.routers.auth import get_current_user, get_admin_user
from app.schemas import AdhocPaymentCreate, AdhocPaymentUpdate, ModelCreate, ModelUpdate
from app.importers.excel_importer import ImportOptions, RunOptions, import_from_excel

router = APIRouter(prefix="/models", tags=["Models"])

_DECIMAL_PLACES = Decimal("0.01")


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

    models = crud.list_models(
        db,
        code=code_filter,
        status=status_filter,
        frequency=frequency_filter,
        payment_method=method_filter,
    )

    totals_map = crud.total_paid_by_model(db, [model.id for model in models])
    total_paid_sum = sum(totals_map.values(), Decimal("0")) if totals_map else Decimal("0")
    payment_methods = crud.list_payment_methods(db)

    # Count models per payment method for the current (filtered) list
    method_counts: dict[str, int] = {}
    for model in models:
        method = (model.payment_method or "").strip()
        if method:
            method_counts[method] = method_counts.get(method, 0) + 1

    # Count models per payment frequency for the current (filtered) list
    frequency_counts: dict[str, int] = {}
    for model in models:
        freq = (model.payment_frequency or "").lower()
        if freq:
            frequency_counts[freq] = frequency_counts.get(freq, 0) + 1

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

    context: dict[str, Any] = {
        "request": request,
        "user": user,
        "models": models,
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
        "total_paid_sum": total_paid_sum,
        "export_url": export_url,
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
    context = _build_model_list_context(request, user, db, code, status, frequency, payment_method)
    return templates.TemplateResponse("models/list.html", context)


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
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    payouts = crud.list_payouts_for_model(db, model_id)

    run_ids = {payout.schedule_run_id for payout in payouts if payout.schedule_run_id}
    runs_map: dict[int, ScheduleRun] = {}
    if run_ids:
        runs = db.execute(select(ScheduleRun).where(ScheduleRun.id.in_(run_ids))).scalars().all()
        runs_map = {run.id: run for run in runs}

    total_paid = Decimal("0")
    latest_pay_date: date | None = None
    payout_rows: list[dict[str, Any]] = []

    for payout in payouts:
        amount = Decimal(payout.amount or 0)
        if payout.status == "paid":
            total_paid += amount

        pay_date = payout.pay_date
        if pay_date and (latest_pay_date is None or pay_date > latest_pay_date):
            latest_pay_date = pay_date

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
        "count": len(payout_rows),
        "total_paid": str(total_paid),
        "total_paid_value": float(total_paid),
        "latest_pay_date": latest_pay_date.isoformat() if latest_pay_date else None,
        "latest_pay_date_display": format_display_date(latest_pay_date) if latest_pay_date else None,
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
        }
    )


@router.get("/new")
def new_model_form(request: Request, user: User = Depends(get_admin_user)):
    return templates.TemplateResponse(
        "models/form.html",
        {
            "request": request,
            "user": user,
            "action": "create",
        },
    )


@router.post("/new")
def create_model(
    request: Request,
    status: str = Form(...),
    code: str = Form(...),
    real_name: str = Form(...),
    working_name: str = Form(...),
    start_date: str = Form(...),
    payment_method: str = Form(...),
    payment_frequency: str = Form(...),
    amount_monthly: str = Form(...),
    crypto_wallet: str = Form(None),
    adjustment_effective_dates: list[str] = Form([]),
    adjustment_amounts: list[str] = Form([]),
    adjustment_notes: list[str] = Form([]),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
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
    
    # Get total paid amount for this model (from scheduled payouts)
    total_paid = crud.total_paid_by_model(db, [model.id]).get(model.id, Decimal("0"))
    
    # Get paid payouts (unified source of truth for payment history)
    paid_payouts = crud.get_paid_payouts_for_model(db, model_id)
    adhoc_payments = crud.list_adhoc_payments(db, model_id)
    error_message = request.query_params.get("error")
    success_message = request.query_params.get("success")
    
    # Cash advances context
    advances = crud.list_advances_for_model(db, model.id)
    advances_outstanding = crud.outstanding_advance_total(db, model.id)

    return templates.TemplateResponse(
        "models/view.html",
        {
            "request": request,
            "user": user,
            "model": model,
            "total_paid": total_paid,
            "paid_payouts": paid_payouts,
            "adhoc_payments": adhoc_payments,
            "advances": advances,
            "advances_outstanding": advances_outstanding,
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

    update_payload = AdhocPaymentUpdate(notes=notes.strip() if notes else None)
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
    return templates.TemplateResponse(
        "models/form.html",
        {
            "request": request,
            "user": user,
            "action": "edit",
            "model": model,
        },
    )


@router.post("/{model_id}/edit")
def update_model(
    model_id: int,
    request: Request,
    status: str = Form(...),
    code: str = Form(...),
    real_name: str = Form(...),
    working_name: str = Form(...),
    start_date: str = Form(...),
    payment_method: str = Form(...),
    payment_frequency: str = Form(...),
    amount_monthly: str = Form(...),
    crypto_wallet: str = Form(None),
    adjustment_effective_dates: list[str] = Form([]),
    adjustment_amounts: list[str] = Form([]),
    adjustment_notes: list[str] = Form([]),
    db: Session = Depends(get_session),
    user: User = Depends(get_admin_user),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

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

    return RedirectResponse(url="/models", status_code=303)


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

    context = _build_model_list_context(request, user, db, None, None, None, None, extra_context)
    return templates.TemplateResponse("models/list.html", context)

