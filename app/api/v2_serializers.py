"""JSON serializers for API v2."""
from __future__ import annotations

import json
from decimal import Decimal

from app.api.serializers import _money, _parse_frequency_counts, _rate
from app.models import (
    AdhocPayment,
    AdvanceRepayment,
    Model,
    ModelAdvance,
    ModelCompensationAdjustment,
    Payout,
    PayoutAdvanceAllocation,
    ScheduleRun,
    ValidationIssue,
)
from app.time_utils import iso_datetime_z


def serialize_v2_model(model: Model) -> dict:
    return {
        "id": model.id,
        "status": model.status,
        "code": model.code,
        "real_name": model.real_name,
        "working_name": model.working_name,
        "start_date": model.start_date.isoformat(),
        "payment_method": model.payment_method,
        "payment_frequency": model.payment_frequency,
        "amount_monthly": _money(model.amount_monthly),
        "crypto_wallet": model.crypto_wallet,
        "created_at": iso_datetime_z(model.created_at),
        "updated_at": iso_datetime_z(model.updated_at),
    }


def serialize_v2_payout(payout: Payout) -> dict:
    wallet = payout.model.crypto_wallet if payout.model else None
    gross = payout.gross_amount if payout.gross_amount is not None else payout.amount
    net = payout.net_amount if payout.net_amount is not None else payout.amount
    deduction = payout.advance_deduction_amount if payout.advance_deduction_amount is not None else Decimal("0")
    return {
        "id": payout.id,
        "schedule_run_id": payout.schedule_run_id,
        "model_id": payout.model_id,
        "pay_date": payout.pay_date.isoformat(),
        "code": payout.code,
        "real_name": payout.real_name,
        "working_name": payout.working_name,
        "payment_method": payout.payment_method,
        "payment_frequency": payout.payment_frequency,
        "gross_amount": _money(gross),
        "advance_deduction_amount": _money(deduction),
        "net_amount": _money(net),
        "amount": _money(net),
        "breakdown_source": payout.breakdown_source,
        "status": payout.status,
        "notes": payout.notes,
        "superseded_at": iso_datetime_z(payout.superseded_at),
        "current_model_crypto_wallet": wallet,
    }


def serialize_v2_schedule_run(run: ScheduleRun) -> dict:
    counts = _parse_frequency_counts(run.summary_frequency_counts)
    normalized = {str(k): int(v) for k, v in counts.items()}
    return {
        "id": run.id,
        "target_year": run.target_year,
        "target_month": run.target_month,
        "currency": run.currency,
        "include_inactive": run.include_inactive,
        "summary_models_paid": run.summary_models_paid,
        "summary_total_payout": _money(run.summary_total_payout),
        "summary_frequency_counts": normalized,
        "created_at": iso_datetime_z(run.created_at),
    }


def serialize_v2_validation_issue(issue: ValidationIssue) -> dict:
    return {
        "id": issue.id,
        "schedule_run_id": issue.schedule_run_id,
        "model_id": issue.model_id,
        "severity": issue.severity,
        "issue": issue.issue,
    }


def serialize_v2_adhoc(payment: AdhocPayment) -> dict:
    return {
        "id": payment.id,
        "model_id": payment.model_id,
        "pay_date": payment.pay_date.isoformat(),
        "amount": _money(payment.amount),
        "description": payment.description,
        "notes": payment.notes,
        "status": payment.status,
        "created_at": iso_datetime_z(payment.created_at),
        "updated_at": iso_datetime_z(payment.updated_at),
    }


def serialize_v2_adjustment(adjustment: ModelCompensationAdjustment) -> dict:
    return {
        "id": adjustment.id,
        "model_id": adjustment.model_id,
        "effective_date": adjustment.effective_date.isoformat(),
        "amount_monthly": _money(adjustment.amount_monthly),
        "notes": adjustment.notes,
        "created_at": iso_datetime_z(adjustment.created_at),
    }


def serialize_v2_advance(advance: ModelAdvance) -> dict:
    return {
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
        "created_at": iso_datetime_z(advance.created_at),
        "updated_at": iso_datetime_z(advance.updated_at),
        "activated_at": iso_datetime_z(advance.activated_at),
    }


def serialize_v2_repayment(repayment: AdvanceRepayment) -> dict:
    return {
        "id": repayment.id,
        "advance_id": repayment.advance_id,
        "payout_id": repayment.payout_id,
        "amount": _money(repayment.amount),
        "source": repayment.source,
        "created_at": iso_datetime_z(repayment.created_at),
    }


def serialize_v2_allocation(allocation: PayoutAdvanceAllocation) -> dict:
    return {
        "id": allocation.id,
        "schedule_run_id": allocation.schedule_run_id,
        "payout_id": allocation.payout_id,
        "model_id": allocation.model_id,
        "advance_id": allocation.advance_id,
        "planned_amount": _money(allocation.planned_amount),
        "created_at": iso_datetime_z(allocation.created_at),
    }
