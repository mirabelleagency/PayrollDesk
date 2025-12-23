"""Snapshot helpers for enabling undo/rollback flows."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Sequence

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud
from app.crud import ReferralTermPayload
from app.models import (
    Model,
    ModelSnapshot,
    ModelCompensationAdjustment,
    Payout,
    PayoutAdvanceAllocation,
    ScheduleRun,
    ScheduleRunSnapshot,
    ValidationIssue,
)
from app.schemas import ModelUpdate

SNAPSHOT_VERSION = 1
MODEL_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "status",
    "code",
    "real_name",
    "working_name",
    "start_date",
    "payment_method",
    "payment_frequency",
    "amount_monthly",
    "crypto_wallet",
    "referred_by_model_id",
    "commission_active",
    "commission_per_referral",
    "commission_payout_frequency",
    "commission_duration_months",
    "commission_status",
)
SCHEDULE_RUN_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "target_year",
    "target_month",
    "currency",
    "include_inactive",
    "summary_models_paid",
    "summary_total_payout",
    "summary_frequency_counts",
    "export_path",
)


class SnapshotError(Exception):
    """Raised when a snapshot operation cannot be completed."""


def capture_model_snapshot(
    db: Session,
    model: Model,
    *,
    actor: str | None = None,
    reason: str = "edit",
) -> ModelSnapshot:
    """Persist the current state of ``model`` so it can be restored later."""

    if not model.id:
        raise SnapshotError("Cannot capture a snapshot for an unsaved model.")

    payload = {
        "version": SNAPSHOT_VERSION,
        "model": _serialize_model_fields(model),
        "adjustments": _serialize_adjustments(model),
        "referral_terms": _serialize_referral_terms(model),
    }
    snapshot = ModelSnapshot(
        model_id=model.id,
        payload=json.dumps(payload, separators=(",", ":")),
        created_by=actor,
        reason=reason,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def restore_latest_model_snapshot(
    db: Session,
    model: Model,
    *,
    actor: str | None = None,
) -> ModelSnapshot:
    """Restore the most recent snapshot for ``model``."""

    if not model.id:
        raise SnapshotError("Cannot restore snapshots for an unsaved model.")

    snapshot = (
        db.query(ModelSnapshot)
        .filter(ModelSnapshot.model_id == model.id)
        .order_by(ModelSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        raise SnapshotError("No earlier versions are available for this model.")

    payload = json.loads(snapshot.payload)
    _apply_snapshot_payload(db, model, payload)
    db.delete(snapshot)
    db.commit()
    return snapshot


def _serialize_model_fields(model: Model) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for field in MODEL_SNAPSHOT_FIELDS:
        value = getattr(model, field)
        serialized[field] = _encode_value(value)
    return serialized


def _serialize_adjustments(model: Model) -> list[dict[str, Any]]:
    adjustments: list[dict[str, Any]] = []
    for adjustment in sorted(model.compensation_adjustments, key=lambda adj: adj.effective_date):
        adjustments.append(
            {
                "effective_date": adjustment.effective_date.isoformat(),
                "amount_monthly": _encode_value(adjustment.amount_monthly),
                "notes": adjustment.notes,
            }
        )
    return adjustments


def _serialize_referral_terms(model: Model) -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    for term in model.referral_terms:
        terms.append(
            {
                "referral_model_id": term.referral_model_id,
                "commission_per_referral": _encode_value(term.commission_per_referral),
                "commission_payout_frequency": term.commission_payout_frequency,
                "commission_duration_months": term.commission_duration_months,
                "is_active": term.is_active,
            }
        )
    return terms


def _encode_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _apply_snapshot_payload(db: Session, model: Model, payload: dict[str, Any]) -> None:
    try:
        schema = ModelUpdate(**payload.get("model", {}))
    except ValidationError as exc:  # pragma: no cover - defensive guard
        raise SnapshotError("Snapshot payload is invalid or incomplete.") from exc
    sanitized = schema.model_dump()
    for field, value in sanitized.items():
        setattr(model, field, value)
    model.updated_at = datetime.now()
    db.add(model)
    db.flush()

    _replace_adjustments(db, model, payload.get("adjustments", []))
    _replace_referral_terms(db, model, payload.get("referral_terms", []))


def _replace_adjustments(db: Session, model: Model, raw_adjustments: Sequence[dict[str, Any]]) -> None:
    db.query(ModelCompensationAdjustment).filter(ModelCompensationAdjustment.model_id == model.id).delete(synchronize_session=False)
    db.flush()

    for entry in raw_adjustments:
        effective_date = date.fromisoformat(entry["effective_date"])
        amount = Decimal(str(entry["amount_monthly"]))
        notes = entry.get("notes")
        crud.create_compensation_adjustment(db, model, effective_date, amount, notes)


def _replace_referral_terms(db: Session, model: Model, entries: Iterable[dict[str, Any]]) -> None:
    payloads: list[ReferralTermPayload] = []
    for entry in entries:
        payloads.append(
            ReferralTermPayload(
                referral_model_id=int(entry["referral_model_id"]),
                commission_per_referral=Decimal(str(entry["commission_per_referral"])) if entry.get("commission_per_referral") is not None else Decimal("0"),
                commission_payout_frequency=entry["commission_payout_frequency"],
                commission_duration_months=entry.get("commission_duration_months"),
                is_active=bool(entry.get("is_active", True)),
            )
        )
    crud.upsert_referral_terms(db, model, payloads)
    db.flush()


def capture_schedule_run_snapshot(
    db: Session,
    run: ScheduleRun,
    *,
    actor: str | None = None,
    reason: str = "regenerate",
) -> ScheduleRunSnapshot:
    """Capture schedule run state prior to regeneration so it can be restored."""

    if not run.id:
        raise SnapshotError("Cannot capture a snapshot for an unsaved schedule run.")

    payouts = list(run.payouts)
    validations = list(run.validations)
    payload = {
        "version": SNAPSHOT_VERSION,
        "run": _serialize_schedule_run(run),
        "payouts": [_serialize_payout(p) for p in payouts],
        "validations": [_serialize_validation(issue) for issue in validations],
        "advance_allocations": _serialize_allocations(db, run.id, payouts),
    }
    snapshot = ScheduleRunSnapshot(
        schedule_run_id=run.id,
        payload=json.dumps(payload, separators=(",", ":")),
        created_by=actor,
        reason=reason,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def restore_latest_schedule_snapshot(
    db: Session,
    run: ScheduleRun,
    *,
    actor: str | None = None,
) -> ScheduleRunSnapshot:
    """Restore the most recent snapshot for a schedule run."""

    if not run.id:
        raise SnapshotError("Cannot restore snapshots for an unsaved schedule run.")

    snapshot = (
        db.query(ScheduleRunSnapshot)
        .filter(ScheduleRunSnapshot.schedule_run_id == run.id)
        .order_by(ScheduleRunSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        raise SnapshotError("No earlier versions are available for this payroll cycle.")

    payload = json.loads(snapshot.payload)
    _apply_schedule_snapshot(db, run, payload)
    db.delete(snapshot)
    db.commit()
    return snapshot


def get_schedule_snapshot_preview(
    db: Session,
    run: ScheduleRun,
    *,
    current_payouts: Sequence[Payout] | None = None,
) -> dict[str, Any] | None:
    """Return metadata about the latest snapshot for display prior to undo."""

    if not run.id:
        return None

    snapshot = (
        db.query(ScheduleRunSnapshot)
        .filter(ScheduleRunSnapshot.schedule_run_id == run.id)
        .order_by(ScheduleRunSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        return None

    payload = json.loads(snapshot.payload)
    run_payload = payload.get("run", {})
    payouts = payload.get("payouts", [])
    validations = payload.get("validations", [])
    allocations = payload.get("advance_allocations", [])
    preview = {
        "captured_at": snapshot.created_at,
        "captured_by": snapshot.created_by,
        "reason": snapshot.reason,
        "payout_count": len(payouts),
        "validation_count": len(validations),
        "allocation_count": len(allocations),
        "summary_models_paid": run_payload.get("summary_models_paid"),
        "summary_total_payout": Decimal(str(run_payload.get("summary_total_payout") or 0)),
        "currency": run_payload.get("currency"),
    }

    payouts_now: Sequence[Payout] = list(current_payouts) if current_payouts is not None else list(run.payouts)
    diff_summary = _build_snapshot_diff_summary(payouts, payouts_now)
    preview["diff"] = diff_summary
    return preview


def _serialize_schedule_run(run: ScheduleRun) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for field in SCHEDULE_RUN_SNAPSHOT_FIELDS:
        serialized[field] = _encode_value(getattr(run, field))
    return serialized


def _serialize_payout(payout: Payout) -> dict[str, Any]:
    return {
        "uid": _build_payout_uid(
            payout.code,
            payout.pay_date,
            payout.payment_method,
            payout.payment_frequency,
        ),
        "model_id": payout.model_id,
        "pay_date": payout.pay_date.isoformat() if payout.pay_date else None,
        "code": payout.code,
        "real_name": payout.real_name,
        "working_name": payout.working_name,
        "payment_method": payout.payment_method,
        "payment_frequency": payout.payment_frequency,
        "amount": _encode_value(payout.amount),
        "notes": payout.notes,
        "status": payout.status,
    }


def _serialize_validation(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "model_id": issue.model_id,
        "severity": issue.severity,
        "issue": issue.issue,
    }


def _serialize_allocations(db: Session, run_id: int, payouts: Sequence[Payout]) -> list[dict[str, Any]]:
    payout_lookup = {p.id: _build_payout_uid(p.code, p.pay_date, p.payment_method, p.payment_frequency) for p in payouts}
    allocations = (
        db.query(PayoutAdvanceAllocation)
        .filter(PayoutAdvanceAllocation.schedule_run_id == run_id)
        .all()
    )
    serialized: list[dict[str, Any]] = []
    for alloc in allocations:
        uid = payout_lookup.get(alloc.payout_id)
        if not uid:
            continue
        serialized.append(
            {
                "payout_uid": uid,
                "model_id": alloc.model_id,
                "advance_id": alloc.advance_id,
                "planned_amount": _encode_value(alloc.planned_amount),
            }
        )
    return serialized


def _apply_schedule_snapshot(db: Session, run: ScheduleRun, payload: dict[str, Any]) -> None:
    for field in SCHEDULE_RUN_SNAPSHOT_FIELDS:
        value = payload.get("run", {}).get(field)
        if field == "summary_total_payout" and value is not None:
            value = Decimal(str(value))
        setattr(run, field, value)
    db.add(run)
    db.flush()

    crud.clear_schedule_data(db, run)

    raw_payouts = payload.get("payouts", [])
    payout_objects: list[Payout] = []
    uid_map: dict[str, Payout] = {}
    for entry in raw_payouts:
        pay_date_value = entry.get("pay_date")
        payout = Payout(
            schedule_run_id=run.id,
            model_id=entry.get("model_id"),
            pay_date=date.fromisoformat(pay_date_value) if pay_date_value else None,
            code=entry.get("code"),
            real_name=entry.get("real_name"),
            working_name=entry.get("working_name"),
            payment_method=entry.get("payment_method"),
            payment_frequency=entry.get("payment_frequency"),
            amount=Decimal(str(entry.get("amount") or 0)),
            notes=entry.get("notes"),
            status=entry.get("status", "not_paid"),
        )
        payout_objects.append(payout)
        uid_map[entry.get("uid")] = payout

    if payout_objects:
        db.add_all(payout_objects)
        db.flush()

    allocation_entries = payload.get("advance_allocations", [])
    allocation_objects: list[PayoutAdvanceAllocation] = []
    for entry in allocation_entries:
        payout = uid_map.get(entry.get("payout_uid"))
        if not payout:
            continue
        allocation_objects.append(
            PayoutAdvanceAllocation(
                schedule_run_id=run.id,
                payout_id=payout.id,
                model_id=entry.get("model_id"),
                advance_id=entry.get("advance_id"),
                planned_amount=Decimal(str(entry.get("planned_amount") or 0)),
            )
        )
    if allocation_objects:
        db.add_all(allocation_objects)

    validation_entries = payload.get("validations", [])
    validation_objects = [
        ValidationIssue(
            schedule_run_id=run.id,
            model_id=entry.get("model_id"),
            severity=entry.get("severity", "info"),
            issue=entry.get("issue", ""),
        )
        for entry in validation_entries
    ]
    if validation_objects:
        db.add_all(validation_objects)


def _build_payout_uid(code: str, pay_date: date | None, method: str, frequency: str) -> str:
    date_value = pay_date.isoformat() if pay_date else ""
    method_value = method or ""
    frequency_value = frequency or ""
    return f"{code}|{date_value}|{method_value}|{frequency_value}"


DIFF_PREVIEW_LIMIT = 6


def _build_snapshot_diff_summary(
    snapshot_entries: Sequence[dict[str, Any]],
    current_payouts: Sequence[Payout],
) -> dict[str, Any]:
    current_map: dict[str, Payout] = {}
    for payout in current_payouts:
        uid = _build_payout_uid(
            payout.code or "",
            payout.pay_date,
            payout.payment_method or "",
            payout.payment_frequency or "",
        )
        current_map[uid] = payout

    snapshot_map: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for entry in snapshot_entries:
        uid = entry.get("uid") or _build_payout_uid(
            entry.get("code") or "",
            _safe_parse_date(entry.get("pay_date")),
            entry.get("payment_method") or "",
            entry.get("payment_frequency") or "",
        )
        snapshot_map[uid] = entry
        payout = current_map.get(uid)
        snapshot_amount = Decimal(str(entry.get("amount") or 0))
        snapshot_status = entry.get("status")
        snapshot_notes = entry.get("notes")
        snapshot_pay_date = _safe_parse_date(entry.get("pay_date"))
        if not payout:
            missing.append(
                {
                    "code": entry.get("code"),
                    "pay_date": snapshot_pay_date,
                    "amount_snapshot": snapshot_amount,
                    "status_snapshot": snapshot_status,
                    "notes_snapshot": snapshot_notes,
                }
            )
            continue

        current_amount = Decimal(str(payout.amount or 0))
        current_status = payout.status
        current_notes = payout.notes
        if (
            snapshot_amount != current_amount
            or (snapshot_status or "") != (current_status or "")
            or (snapshot_notes or "") != (current_notes or "")
        ):
            changed.append(
                {
                    "code": entry.get("code"),
                    "pay_date": snapshot_pay_date or payout.pay_date,
                    "amount_snapshot": snapshot_amount,
                    "amount_current": current_amount,
                    "status_snapshot": snapshot_status,
                    "status_current": current_status,
                    "notes_snapshot": snapshot_notes,
                    "notes_current": current_notes,
                }
            )

    extra: list[dict[str, Any]] = []
    for uid, payout in current_map.items():
        if uid in snapshot_map:
            continue
        extra.append(
            {
                "code": payout.code,
                "pay_date": payout.pay_date,
                "amount_current": Decimal(str(payout.amount or 0)),
                "status_current": payout.status,
                "notes_current": payout.notes,
            }
        )

    counts = {
        "missing": len(missing),
        "changed": len(changed),
        "extra": len(extra),
    }
    limit = DIFF_PREVIEW_LIMIT
    preview = {
        "missing": missing[:limit],
        "changed": changed[:limit],
        "extra": extra[:limit],
        "counts": counts,
        "more": {
            "missing": max(0, counts["missing"] - min(counts["missing"], limit)),
            "changed": max(0, counts["changed"] - min(counts["changed"], limit)),
            "extra": max(0, counts["extra"] - min(counts["extra"], limit)),
        },
        "has_diff": any(counts.values()),
    }
    return preview


def _safe_parse_date(raw: Any) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except Exception:
        return None
