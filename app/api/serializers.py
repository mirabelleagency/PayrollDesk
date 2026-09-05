"""JSON serializers for the external API (decimal strings, ISO dates)."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.models import (
    AdhocPayment,
    AdvanceRepayment,
    ApiKey,
    Model,
    ModelAdvance,
    ModelCompensationAdjustment,
    Payout,
    PayoutAdvanceAllocation,
    ScheduleRun,
    ValidationIssue,
)


def _money(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rate(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _iso_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_frequency_counts(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def serialize_model(model: Model) -> dict[str, Any]:
    return {
        "id": model.id,
        "status": model.status,
        "code": model.code,
        "real_name": model.real_name,
        "working_name": model.working_name,
        "start_date": _iso_date(model.start_date),
        "payment_method": model.payment_method,
        "payment_frequency": model.payment_frequency,
        "amount_monthly": _money(model.amount_monthly),
        "crypto_wallet": model.crypto_wallet,
        "created_at": _iso_datetime(model.created_at),
        "updated_at": _iso_datetime(model.updated_at),
    }


def serialize_payout(payout: Payout) -> dict[str, Any]:
    wallet = payout.model.crypto_wallet if payout.model else None
    return {
        "id": payout.id,
        "schedule_run_id": payout.schedule_run_id,
        "model_id": payout.model_id,
        "pay_date": _iso_date(payout.pay_date),
        "code": payout.code,
        "real_name": payout.real_name,
        "working_name": payout.working_name,
        "payment_method": payout.payment_method,
        "payment_frequency": payout.payment_frequency,
        "amount": _money(payout.amount),
        "status": payout.status,
        "notes": payout.notes,
        "crypto_wallet": wallet,
    }


def serialize_schedule_run(run: ScheduleRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "target_year": run.target_year,
        "target_month": run.target_month,
        "currency": run.currency,
        "include_inactive": run.include_inactive,
        "summary_models_paid": run.summary_models_paid,
        "summary_total_payout": _money(run.summary_total_payout),
        "summary_frequency_counts": _parse_frequency_counts(run.summary_frequency_counts),
        "export_path": run.export_path,
        "created_at": _iso_datetime(run.created_at),
    }


def serialize_validation_issue(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "schedule_run_id": issue.schedule_run_id,
        "model_id": issue.model_id,
        "severity": issue.severity,
        "issue": issue.issue,
    }


def serialize_adhoc_payment(payment: AdhocPayment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "model_id": payment.model_id,
        "pay_date": _iso_date(payment.pay_date),
        "amount": _money(payment.amount),
        "description": payment.description,
        "notes": payment.notes,
        "status": payment.status,
        "created_at": _iso_datetime(payment.created_at),
        "updated_at": _iso_datetime(payment.updated_at),
    }


def serialize_adjustment(adjustment: ModelCompensationAdjustment) -> dict[str, Any]:
    return {
        "id": adjustment.id,
        "model_id": adjustment.model_id,
        "effective_date": _iso_date(adjustment.effective_date),
        "amount_monthly": _money(adjustment.amount_monthly),
        "notes": adjustment.notes,
        "created_at": _iso_datetime(adjustment.created_at),
        "created_by": adjustment.created_by,
    }


def serialize_advance(advance: ModelAdvance, *, include_repayments: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": advance.id,
        "model_id": advance.model_id,
        "amount_total": _money(advance.amount_total),
        "amount_remaining": _money(advance.amount_remaining),
        "status": advance.status,
        "strategy": advance.strategy,
        "fixed_amount": _money(advance.fixed_amount) if advance.fixed_amount is not None else None,
        "percent_rate": _rate(advance.percent_rate),
        "min_net_floor": _money(advance.min_net_floor),
        "max_per_run": _money(advance.max_per_run),
        "cap_multiplier": _rate(advance.cap_multiplier),
        "notes": advance.notes,
        "created_at": _iso_datetime(advance.created_at),
        "updated_at": _iso_datetime(advance.updated_at),
        "activated_at": _iso_datetime(advance.activated_at),
    }
    if include_repayments:
        payload["repayments"] = [serialize_advance_repayment(r) for r in (advance.repayments or [])]
    return payload


def serialize_advance_repayment(repayment: AdvanceRepayment) -> dict[str, Any]:
    return {
        "id": repayment.id,
        "advance_id": repayment.advance_id,
        "payout_id": repayment.payout_id,
        "amount": _money(repayment.amount),
        "source": repayment.source,
        "created_at": _iso_datetime(repayment.created_at),
    }


def serialize_advance_allocation(allocation: PayoutAdvanceAllocation) -> dict[str, Any]:
    return {
        "id": allocation.id,
        "schedule_run_id": allocation.schedule_run_id,
        "payout_id": allocation.payout_id,
        "model_id": allocation.model_id,
        "advance_id": allocation.advance_id,
        "planned_amount": _money(allocation.planned_amount),
        "created_at": _iso_datetime(allocation.created_at),
    }


def serialize_api_key_meta(api_key: ApiKey) -> dict[str, Any]:
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "created_at": _iso_datetime(api_key.created_at),
        "last_used_at": _iso_datetime(api_key.last_used_at),
        "revoked_at": _iso_datetime(api_key.revoked_at),
        "created_by": api_key.created_by,
    }
