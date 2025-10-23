"""Database access helpers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Sequence

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.payroll import ModelRecord, ValidationMessage
from app.models import (
    AdhocPayment,
    Model,
    ModelCompensationAdjustment,
    Payout,
    ScheduleRun,
    ValidationIssue,
    AuditLog,
    ModelAdvance,
    AdvanceRepayment,
    PayoutAdvanceAllocation,
)
from app.schemas import AdhocPaymentCreate, AdhocPaymentUpdate, ModelCreate, ModelUpdate
from sqlalchemy import distinct
from decimal import Decimal

# --- Defaults for advances policy knobs ---
ADVANCE_DEFAULT_MIN_FLOOR = Decimal("500")
ADVANCE_DEFAULT_MAX_PER_RUN = Decimal("600")
ADVANCE_DEFAULT_CAP_MULTIPLIER = Decimal("1.0")


def list_models(
    db: Session,
    code: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
) -> Sequence[Model]:
    stmt = select(Model)

    if code:
        like_value = f"%{code.strip()}%"
        stmt = stmt.where(Model.code.ilike(like_value))

    if status:
        stmt = stmt.where(Model.status == status)

    if frequency:
        stmt = stmt.where(Model.payment_frequency == frequency)

    if payment_method:
        stmt = stmt.where(Model.payment_method == payment_method)

    stmt = stmt.order_by(Model.code)
    return db.execute(stmt).scalars().all()


def get_model(db: Session, model_id: int) -> Model | None:
    return db.get(Model, model_id)


def get_model_by_code(db: Session, code: str) -> Model | None:
    stmt = select(Model).where(Model.code == code)
    return db.execute(stmt).scalars().first()


def create_model(db: Session, payload: ModelCreate) -> Model:
    model = Model(**payload.model_dump())
    db.add(model)
    db.flush()

    effective_date = model.start_date or date.today()
    existing_adjustment = (
        db.query(ModelCompensationAdjustment)
        .filter(
            ModelCompensationAdjustment.model_id == model.id,
            ModelCompensationAdjustment.effective_date == effective_date,
        )
        .first()
    )
    if not existing_adjustment:
        create_compensation_adjustment(
            db,
            model,
            effective_date=effective_date,
            amount_monthly=Decimal(model.amount_monthly),
            notes="Initial compensation",
        )
    db.commit()
    db.refresh(model)
    return model


def update_model(db: Session, model: Model, payload: ModelUpdate) -> Model:
    for key, value in payload.model_dump().items():
        setattr(model, key, value)
    model.updated_at = datetime.now()
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def delete_model(db: Session, model: Model) -> None:
    db.delete(model)
    db.commit()


def get_effective_compensation_amount(db: Session, model: Model, target_date: date) -> Decimal:
    adjustment = (
        db.query(ModelCompensationAdjustment)
        .filter(
            ModelCompensationAdjustment.model_id == model.id,
            ModelCompensationAdjustment.effective_date <= target_date,
        )
        .order_by(ModelCompensationAdjustment.effective_date.desc())
        .first()
    )
    if adjustment:
        return Decimal(adjustment.amount_monthly)
    return Decimal(model.amount_monthly)


def create_compensation_adjustment(
    db: Session,
    model: Model,
    effective_date: date,
    amount_monthly: Decimal,
    notes: str | None = None,
) -> ModelCompensationAdjustment:
    adjustment = (
        db.query(ModelCompensationAdjustment)
        .filter(
            ModelCompensationAdjustment.model_id == model.id,
            ModelCompensationAdjustment.effective_date == effective_date,
        )
        .first()
    )
    if adjustment:
        adjustment.amount_monthly = amount_monthly
        adjustment.notes = notes
    else:
        adjustment = ModelCompensationAdjustment(
            model_id=model.id,
            effective_date=effective_date,
            amount_monthly=amount_monthly,
            notes=notes,
        )
        db.add(adjustment)

    if effective_date <= date.today():
        model.amount_monthly = amount_monthly
        model.updated_at = datetime.now()
        db.add(model)

    db.flush()
    return adjustment


def clear_schedule_data(db: Session, schedule_run: ScheduleRun) -> None:
    # Delete allocations linked to this run first to avoid stale planned deductions
    db.query(PayoutAdvanceAllocation).filter(PayoutAdvanceAllocation.schedule_run_id == schedule_run.id).delete(synchronize_session=False)
    db.query(Payout).filter(Payout.schedule_run_id == schedule_run.id).delete()
    db.query(ValidationIssue).filter(ValidationIssue.schedule_run_id == schedule_run.id).delete()
    db.commit()


def create_schedule_run(
    db: Session,
    target_year: int,
    target_month: int,
    currency: str,
    include_inactive: bool,
    summary: dict,
    export_path: str,
) -> ScheduleRun:
    existing = (
        db.query(ScheduleRun)
        .filter(
            ScheduleRun.target_year == target_year,
            ScheduleRun.target_month == target_month,
        )
        .order_by(ScheduleRun.created_at.desc())
        .first()
    )
    if existing:
        raise ValueError(
            f"A schedule run already exists for {target_year:04d}-{target_month:02d} (id {existing.id})."
        )
    run = ScheduleRun(
        target_year=target_year,
        target_month=target_month,
        currency=currency,
        include_inactive=include_inactive,
        summary_models_paid=summary.get("models_paid", 0),
        summary_total_payout=summary.get("total_payout", 0),
        summary_frequency_counts=json.dumps(summary.get("frequency_counts", {})),
        export_path=export_path,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def store_payouts(db: Session, run: ScheduleRun, payouts: Iterable[dict], amount_column: str, old_payout_data: dict | None = None) -> None:
    """Store payouts, preserving status and notes from previous payouts when available."""
    if old_payout_data is None:
        old_payout_data = {}
    
    objects: list[Payout] = []
    for payout in payouts:
        pay_date = payout["Pay Date"]
        code = payout["Code"]
        key = (code, pay_date)
        
        # Check if this payout existed before - if so, preserve its status and notes
        status = old_payout_data.get(key, {}).get("status", "not_paid")
        notes = old_payout_data.get(key, {}).get("notes", payout.get("Notes"))
        
        payout_obj = Payout(
            schedule_run_id=run.id,
            model_id=_lookup_model_id(db, code),
            pay_date=pay_date,
            code=code,
            real_name=payout["Real Name"],
            working_name=payout["Working Name"],
            payment_method=payout["Payment Method"],
            payment_frequency=payout["Payment Frequency"],
            amount=payout.get(amount_column),
            notes=notes,
            status=status,
        )
        objects.append(payout_obj)
    
    db.add_all(objects)
    # Assign IDs so we can link allocations to payouts
    db.flush()

    # Apply cash advance allocations and adjust payout amounts (net), without posting repayments yet
    _apply_advance_allocations_for_run(db, run, objects)

    db.commit()


def store_validation_messages(
    db: Session,
    run: ScheduleRun,
    records: Iterable[ModelRecord],
    include_inactive: bool,
) -> None:
    issues: list[ValidationIssue] = []
    for record in records:
        is_active = record.status.lower() == "active"
        if not is_active and not include_inactive:
            continue
        for message in record.validation_messages:
            issues.append(
                ValidationIssue(
                    schedule_run_id=run.id,
                    model_id=_lookup_model_id(db, record.code),
                    severity=message.level,
                    issue=message.text,
                )
            )
    if issues:
        db.add_all(issues)
        db.commit()


def _lookup_model_id(db: Session, code: str) -> int | None:
    stmt = select(Model.id).where(Model.code == code)
    return db.execute(stmt).scalar_one_or_none()


def list_schedule_runs(
    db: Session, target_year: int | None = None, target_month: int | None = None
) -> Sequence[ScheduleRun]:
    stmt = select(ScheduleRun)

    if target_year is not None:
        stmt = stmt.where(ScheduleRun.target_year == target_year)

    if target_month is not None:
        stmt = stmt.where(ScheduleRun.target_month == target_month)

    stmt = stmt.order_by(ScheduleRun.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_schedule_run(db: Session, run_id: int) -> ScheduleRun | None:
    return db.get(ScheduleRun, run_id)


def list_payouts_for_run(
    db: Session,
    run_id: int,
    code: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    status: str | None = None,
    pay_date: date | None = None,
) -> Sequence[Payout]:
    stmt = select(Payout).where(
        Payout.schedule_run_id == run_id,
        Payout.model_id.isnot(None),
    )

    if code:
        stmt = stmt.where(Payout.code.ilike(f"%{code.strip()}%"))

    if frequency:
        stmt = stmt.where(Payout.payment_frequency == frequency)

    if payment_method:
        stmt = stmt.where(Payout.payment_method == payment_method)

    if status:
        stmt = stmt.where(Payout.status == status)

    if pay_date:
        stmt = stmt.where(Payout.pay_date == pay_date)

    stmt = stmt.order_by(Payout.pay_date, Payout.code)
    return db.execute(stmt).scalars().all()


def list_payouts_for_model(
    db: Session,
    model_id: int,
    pay_date: date | None = None,
    status: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
) -> Sequence[Payout]:
    stmt = select(Payout).where(Payout.model_id == model_id)

    if pay_date is not None:
        stmt = stmt.where(Payout.pay_date == pay_date)

    if status:
        stmt = stmt.where(Payout.status == status)

    if frequency:
        stmt = stmt.where(Payout.payment_frequency == frequency)

    if payment_method:
        stmt = stmt.where(Payout.payment_method == payment_method)

    stmt = stmt.order_by(Payout.pay_date.desc(), Payout.id.desc())
    return db.execute(stmt).scalars().all()


def list_validation_for_run(db: Session, run_id: int) -> Sequence[ValidationIssue]:
    stmt = select(ValidationIssue).where(ValidationIssue.schedule_run_id == run_id).order_by(
        ValidationIssue.severity, ValidationIssue.id
    )
    return db.execute(stmt).scalars().all()


def get_payout(db: Session, payout_id: int) -> Payout | None:
    return db.get(Payout, payout_id)


def update_payout(db: Session, payout: Payout, note: str | None, status: str) -> None:
    payout.notes = note or None
    payout.status = status
    db.add(payout)
    db.commit()

    # If payout marked as paid, realize any planned allocations as repayments (idempotent)
    if status == "paid":
        _realize_allocations_for_paid_payout(db, payout)
        db.commit()


def delete_schedule_run(db: Session, run: ScheduleRun) -> None:
    db.delete(run)
    db.commit()


def total_paid_by_model(db: Session, model_ids: Sequence[int]) -> dict[int, Decimal]:
    if not model_ids:
        return {}

    stmt = (
        select(Payout.model_id, func.coalesce(func.sum(Payout.amount), 0))
        .where(Payout.model_id.in_(model_ids), Payout.status == "paid")
        .group_by(Payout.model_id)
    )
    results = db.execute(stmt).all()
    totals: dict[int, Decimal] = {}
    for model_id, total in results:
        if isinstance(total, Decimal):
            totals[model_id] = total
        else:
            totals[model_id] = Decimal(total)
    return totals


def list_payment_methods(db: Session) -> list[str]:
    stmt = select(Model.payment_method).distinct().order_by(Model.payment_method)
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def payment_methods_for_run(db: Session, run_id: int) -> list[str]:
    stmt = (
        select(Payout.payment_method)
        .where(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .distinct()
        .order_by(Payout.payment_method)
    )
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def frequencies_for_run(db: Session, run_id: int) -> list[str]:
    stmt = (
        select(Payout.payment_frequency)
        .where(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .distinct()
        .order_by(Payout.payment_frequency)
    )
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def run_payment_summary(db: Session, run_id: int) -> dict[str, Decimal | int]:
    paid_sum_stmt = (
        select(func.coalesce(func.sum(Payout.amount), 0))
        .where(
            Payout.schedule_run_id == run_id,
            Payout.status == "paid",
            Payout.model_id.isnot(None),
        )
    )
    unpaid_sum_stmt = (
        select(func.coalesce(func.sum(Payout.amount), 0))
        .where(
            Payout.schedule_run_id == run_id,
            Payout.status != "paid",
            Payout.model_id.isnot(None),
        )
    )
    # Count unique models that have at least one payout with status "paid"
    paid_models_stmt = (
        select(func.count(func.distinct(Payout.code)))
        .where(
            Payout.schedule_run_id == run_id,
            Payout.status == "paid",
            Payout.model_id.isnot(None),
        )
    )

    paid_total = Decimal(db.execute(paid_sum_stmt).scalar_one() or 0)
    unpaid_total = Decimal(db.execute(unpaid_sum_stmt).scalar_one() or 0)
    paid_models = db.execute(paid_models_stmt).scalar_one() or 0
    total_payout = paid_total + unpaid_total

    overall_paid_stmt = select(func.coalesce(func.sum(Payout.amount), 0)).where(Payout.status == "paid")
    overall_paid_total = Decimal(db.execute(overall_paid_stmt).scalar_one() or 0)

    return {
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "paid_models": int(paid_models),
        "total_payout": total_payout,
        "overall_paid": overall_paid_total,
    }


def payout_status_counts(db: Session, run_id: int) -> dict[str, int]:
    stmt = (
        select(Payout.status, func.count())
        .where(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .group_by(Payout.status)
    )
    return {status: count for status, count in db.execute(stmt).all()}


def payout_codes_for_run(db: Session, run_id: int) -> list[str]:
    stmt = (
        select(Payout.code)
        .where(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .distinct()
        .order_by(Payout.code)
    )
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def payout_dates_for_run(db: Session, run_id: int) -> list[date]:
    stmt = (
        select(Payout.pay_date)
        .where(
            Payout.schedule_run_id == run_id,
            Payout.model_id.isnot(None),
        )
        .distinct()
        .order_by(Payout.pay_date)
    )
    return [row[0] for row in db.execute(stmt).all() if row[0]]


def dashboard_summary(db: Session) -> dict[str, Decimal | int | date | None]:
    total_models = db.execute(select(func.count(Model.id))).scalar_one() or 0
    active_models = db.execute(select(func.count(Model.id)).where(Model.status == "Active")).scalar_one() or 0
    inactive_models = db.execute(select(func.count(Model.id)).where(Model.status == "Inactive")).scalar_one() or 0

    total_runs = db.execute(select(func.count(ScheduleRun.id))).scalar_one() or 0
    latest_run = (
        db.execute(select(ScheduleRun).order_by(ScheduleRun.created_at.desc())).scalars().first()
    )

    today = date.today()
    current_month_run = (
        db.execute(
            select(ScheduleRun)
            .where(
                ScheduleRun.target_year == today.year,
                ScheduleRun.target_month == today.month,
            )
            .order_by(ScheduleRun.created_at.desc())
        )
        .scalars()
        .first()
    )

    run_for_metrics = current_month_run or latest_run

    lifetime_paid_stmt = (
        select(func.coalesce(func.sum(Payout.amount), 0))
        .where(Payout.status == "paid")
        .where(Payout.model_id.isnot(None))
    )
    lifetime_paid = Decimal(db.execute(lifetime_paid_stmt).scalar_one() or 0)

    outstanding_stmt = (
        select(func.coalesce(func.sum(Payout.amount), 0))
        .where(Payout.status != "paid")
        .where(Payout.model_id.isnot(None))
    )
    outstanding_total = Decimal(db.execute(outstanding_stmt).scalar_one() or 0)

    pending_count_stmt = select(func.count()).where(Payout.status == "not_paid").where(Payout.model_id.isnot(None))
    pending_count = db.execute(pending_count_stmt).scalar_one() or 0

    on_hold_count_stmt = select(func.count()).where(Payout.status == "on_hold").where(Payout.model_id.isnot(None))
    on_hold_count = db.execute(on_hold_count_stmt).scalar_one() or 0

    latest_run_paid = Decimal("0")
    latest_run_unpaid = Decimal("0")
    if run_for_metrics:
        latest_paid_stmt = (
            select(func.coalesce(func.sum(Payout.amount), 0))
            .where(Payout.schedule_run_id == run_for_metrics.id, Payout.status == "paid")
            .where(Payout.model_id.isnot(None))
        )
        latest_run_paid = Decimal(db.execute(latest_paid_stmt).scalar_one() or 0)

        latest_unpaid_stmt = (
            select(func.coalesce(func.sum(Payout.amount), 0))
            .where(Payout.schedule_run_id == run_for_metrics.id, Payout.status != "paid")
            .where(Payout.model_id.isnot(None))
        )
        latest_run_unpaid = Decimal(db.execute(latest_unpaid_stmt).scalar_one() or 0)

    # Calculate monthly burn (current month total payout)
    monthly_burn = Decimal("0")
    monthly_unpaid = Decimal("0")
    if current_month_run:
        # Recompute monthly burn from actual payouts with linked models to avoid stale summary totals
        monthly_burn_stmt = (
            select(func.coalesce(func.sum(Payout.amount), 0))
            .where(Payout.schedule_run_id == current_month_run.id)
            .where(Payout.model_id.isnot(None))
        )
        monthly_burn = Decimal(db.execute(monthly_burn_stmt).scalar_one() or 0)
        # Calculate current month unpaid (linked models only)
        monthly_unpaid_stmt = (
            select(func.coalesce(func.sum(Payout.amount), 0))
            .where(Payout.schedule_run_id == current_month_run.id, Payout.status != "paid")
            .where(Payout.model_id.isnot(None))
        )
        monthly_unpaid = Decimal(db.execute(monthly_unpaid_stmt).scalar_one() or 0)

    # Calculate run rate (annualized from monthly burn)
    run_rate = monthly_burn * 12
    
    # Calculate current year total paid
    year_total_paid = Decimal("0")
    year_paid_stmt = (
        select(func.coalesce(func.sum(Payout.amount), 0))
        .join(ScheduleRun, Payout.schedule_run_id == ScheduleRun.id)
        .where(
            Payout.status == "paid",
            Payout.model_id.isnot(None),
            ScheduleRun.target_year == today.year,
        )
    )
    year_total_paid = Decimal(db.execute(year_paid_stmt).scalar_one() or 0)

    # Calculate previous month metrics for comparison
    prev_month = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1
    
    prev_month_run = (
        db.execute(
            select(ScheduleRun)
            .where(
                ScheduleRun.target_year == prev_year,
                ScheduleRun.target_month == prev_month,
            )
            .order_by(ScheduleRun.created_at.desc())
        )
        .scalars()
        .first()
    )
    
    prev_monthly_burn = Decimal("0")
    if prev_month_run:
        prev_monthly_burn = prev_month_run.summary_total_payout or Decimal("0")
    
    # Calculate month-over-month change
    burn_change_pct = None
    if prev_monthly_burn > 0:
        burn_change_pct = ((monthly_burn - prev_monthly_burn) / prev_monthly_burn * 100)

    # Count overdue payments (payments with pay_date in the past and not paid)
    overdue_count = db.execute(
        select(func.count())
        .where(
            Payout.status.in_(["not_paid", "on_hold"]),
            Payout.pay_date < today,
            Payout.model_id.isnot(None),
        )
    ).scalar_one() or 0

    # Get overdue payment details with run IDs
    overdue_payments_stmt = (
        select(Payout, Model)
        .join(Model, Payout.model_id == Model.id)
        .where(
            Payout.status.in_(["not_paid", "on_hold"]),
            Payout.pay_date < today
        )
        .order_by(Payout.pay_date.asc())
        .limit(10)  # Limit to first 10 for dashboard
    )
    overdue_payments_data = []
    for payout, model in db.execute(overdue_payments_stmt).all():
        overdue_payments_data.append({
            "id": payout.id,
            "run_id": payout.schedule_run_id,
            "model_code": model.code,
            "pay_date": payout.pay_date,
            "amount": payout.amount,
        })

    # Get on-hold payment details with run IDs
    on_hold_payments_stmt = (
        select(Payout, Model)
        .join(Model, Payout.model_id == Model.id)
        .where(Payout.status == "on_hold")
        .order_by(Payout.pay_date.asc())
        .limit(10)  # Limit to first 10 for dashboard
    )
    on_hold_payments_data = []
    for payout, model in db.execute(on_hold_payments_stmt).all():
        on_hold_payments_data.append({
            "id": payout.id,
            "run_id": payout.schedule_run_id,
            "model_code": model.code,
            "pay_date": payout.pay_date,
            "amount": payout.amount,
        })

    # Calculate average payout per active model
    avg_per_model = Decimal("0")
    if active_models > 0 and monthly_burn > 0:
        avg_per_model = monthly_burn / active_models

    return {
        "total_models": int(total_models),
        "active_models": int(active_models),
        "inactive_models": int(inactive_models),
        "total_runs": int(total_runs),
    "latest_run": run_for_metrics,
    "latest_run_is_current_month": bool(current_month_run),
        "lifetime_paid": lifetime_paid,
        "outstanding_total": outstanding_total,
        "pending_count": int(pending_count),
        "on_hold_count": int(on_hold_count),
        "latest_run_paid": latest_run_paid,
        "latest_run_unpaid": latest_run_unpaid,
        "monthly_burn": monthly_burn,
        "run_rate": run_rate,
        "year_total_paid": year_total_paid,
        "burn_change_pct": burn_change_pct,
        "overdue_count": int(overdue_count),
        "avg_per_model": avg_per_model,
        "overdue_payments": overdue_payments_data,
        "on_hold_payments": on_hold_payments_data,
    }


def recent_schedule_runs(db: Session, limit: int = 5) -> Sequence[ScheduleRun]:
    stmt = select(ScheduleRun).order_by(ScheduleRun.created_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


def top_paid_models(db: Session, limit: int = 5) -> list[tuple[Model, Decimal]]:
    stmt = (
        select(Model, func.coalesce(func.sum(Payout.amount), 0).label("total_paid"))
        .join(Payout, Payout.model_id == Model.id)
        .where(Payout.status == "paid")
        .group_by(Model.id)
        .order_by(func.coalesce(func.sum(Payout.amount), 0).desc())
        .limit(limit)
    )
    results = db.execute(stmt).all()
    output: list[tuple[Model, Decimal]] = []
    for model, total in results:
        if isinstance(total, Decimal):
            output.append((model, total))
        else:
            output.append((model, Decimal(total)))
    return output


def recent_validation_issues(db: Session, limit: int = 5) -> Sequence[ValidationIssue]:
    stmt = select(ValidationIssue).order_by(ValidationIssue.id.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


def pending_adhoc_payments(db: Session, limit: int = 6) -> Sequence[AdhocPayment]:
    stmt = (
        select(AdhocPayment)
        .options(selectinload(AdhocPayment.model))
        .where(AdhocPayment.status == "pending")
        .order_by(AdhocPayment.pay_date.asc(), AdhocPayment.id.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return db.execute(stmt).scalars().all()


def get_paid_payouts_for_model(db: Session, model_id: int) -> Sequence[Payout]:
    """
    Get all paid payouts for a model, sorted by pay date descending.
    This is the unified source of truth for payment history.
    """
    stmt = (
        select(Payout)
        .where(Payout.model_id == model_id)
        .where(Payout.status == "paid")
        .order_by(Payout.pay_date.desc())
    )
    return db.execute(stmt).scalars().all()


def find_duplicate_payouts(
    db: Session, 
    model_id: int, 
    pay_date: date, 
    amount: Decimal, 
    status: str
) -> Sequence[Payout]:
    """
    Find existing payouts matching the given criteria (date, amount, status).
    Used for duplicate detection.
    """
    stmt = (
        select(Payout)
        .where(Payout.model_id == model_id)
        .where(Payout.pay_date == pay_date)
        .where(Payout.amount == amount)
        .where(Payout.status == status)
    )
    return db.execute(stmt).scalars().all()


def list_adhoc_payments(
    db: Session,
    model_id: int,
    status: str | None = None,
) -> Sequence[AdhocPayment]:
    stmt = select(AdhocPayment).where(AdhocPayment.model_id == model_id)
    if status:
        stmt = stmt.where(AdhocPayment.status == status)
    stmt = stmt.order_by(AdhocPayment.pay_date.desc(), AdhocPayment.id.desc())
    return db.execute(stmt).scalars().all()


def list_adhoc_payments_for_month(
    db: Session,
    year: int,
    month: int,
    status: str | None = None,
) -> Sequence[AdhocPayment]:
    if month < 1 or month > 12:
        raise ValueError("month must be in 1..12")

    month_start = date(year, month, 1)
    if month == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month + 1, 1)

    stmt = (
        select(AdhocPayment)
        .options(selectinload(AdhocPayment.model))
        .where(AdhocPayment.pay_date >= month_start)
        .where(AdhocPayment.pay_date < next_month_start)
    )
    if status:
        stmt = stmt.where(AdhocPayment.status == status)
    stmt = stmt.order_by(AdhocPayment.pay_date.asc(), AdhocPayment.id.asc())
    return db.execute(stmt).scalars().all()


def get_adhoc_payment(db: Session, payment_id: int) -> AdhocPayment | None:
    return db.get(AdhocPayment, payment_id)


def create_adhoc_payment(db: Session, model: Model, payload: AdhocPaymentCreate) -> AdhocPayment:
    payment = AdhocPayment(
        model_id=model.id,
        pay_date=payload.pay_date,
        amount=payload.amount,
        description=(payload.description.strip() if payload.description else None),
        notes=(payload.notes.strip() if payload.notes else None),
        status=payload.status.lower(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def update_adhoc_payment(db: Session, payment: AdhocPayment, payload: AdhocPaymentUpdate) -> AdhocPayment:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field in {"description", "notes"}:
            normalized = value.strip() if isinstance(value, str) else None
            setattr(payment, field, normalized or None)
        elif field == "status" and value is not None:
            setattr(payment, field, value.lower())
        else:
            setattr(payment, field, value)
    payment.updated_at = datetime.now()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def delete_adhoc_payment(db: Session, payment: AdhocPayment) -> None:
    db.delete(payment)
    db.commit()


def set_adhoc_payment_status(db: Session, payment: AdhocPayment, status: str, notes: str | None = None) -> AdhocPayment:
    payment.status = status.lower()
    if notes is not None:
        payment.notes = notes.strip() or None
    payment.updated_at = datetime.now()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


# --- Hard purge helpers ----------------------------------------------------

def get_model_purge_impact(db: Session, model_id: int) -> dict[str, Decimal | int | str]:
    """Compute the rows and amounts that would be removed when purging a model.

    Returns a summary dictionary with counts and amount breakdowns.
    """
    model = get_model(db, model_id)
    if not model:
        raise ValueError("Model not found")

    zero = Decimal("0")

    # Payouts breakdown
    payouts_total = db.execute(
        select(func.count()).where(Payout.model_id == model_id)
    ).scalar_one() or 0
    payouts_paid = db.execute(
        select(func.count()).where(Payout.model_id == model_id, Payout.status == "paid")
    ).scalar_one() or 0
    payouts_unpaid = payouts_total - int(payouts_paid)

    payouts_paid_amount = Decimal(
        db.execute(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.model_id == model_id, Payout.status == "paid"
            )
        ).scalar_one()
        or zero
    )
    payouts_unpaid_amount = Decimal(
        db.execute(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.model_id == model_id, Payout.status != "paid"
            )
        ).scalar_one()
        or zero
    )

    # Distinct runs affected by payouts
    run_ids_impacted = db.execute(
        select(distinct(Payout.schedule_run_id)).where(Payout.model_id == model_id)
    ).scalars().all()
    runs_affected = len(run_ids_impacted)

    # Determine which runs would become empty (no payouts left) after purging this model
    runs_empty_ids: list[int] = []
    for rid in run_ids_impacted:
        # Total payouts currently in the run (all models)
        total_in_run = db.execute(
            select(func.count()).where(Payout.schedule_run_id == rid)
        ).scalar_one() or 0
        # Payouts in the run belonging to this model
        model_in_run = db.execute(
            select(func.count()).where(Payout.schedule_run_id == rid, Payout.model_id == model_id)
        ).scalar_one() or 0
        if total_in_run == model_in_run and total_in_run > 0:
            runs_empty_ids.append(int(rid))

    # Validation issues
    validations_count = db.execute(
        select(func.count()).where(ValidationIssue.model_id == model_id)
    ).scalar_one() or 0

    # Adhoc payments
    adhoc_count = db.execute(
        select(func.count()).where(AdhocPayment.model_id == model_id)
    ).scalar_one() or 0
    adhoc_amount = Decimal(
        db.execute(
            select(func.coalesce(func.sum(AdhocPayment.amount), 0)).where(AdhocPayment.model_id == model_id)
        ).scalar_one()
        or zero
    )

    # Compensation adjustments
    adjustments_count = db.execute(
        select(func.count()).where(ModelCompensationAdjustment.model_id == model_id)
    ).scalar_one() or 0

    return {
        "model_id": model.id,
        "model_code": model.code,
        "payouts_total": int(payouts_total),
        "payouts_paid": int(payouts_paid),
        "payouts_unpaid": int(payouts_unpaid),
        "payouts_paid_amount": payouts_paid_amount,
        "payouts_unpaid_amount": payouts_unpaid_amount,
        "runs_affected": int(runs_affected),
        "runs_empty_after": int(len(runs_empty_ids)),
        "runs_empty_ids": runs_empty_ids,
        "validations": int(validations_count),
        "adhoc_payments": int(adhoc_count),
        "adhoc_amount": adhoc_amount,
        "adjustments": int(adjustments_count),
        "total_rows": int(payouts_total + validations_count + adhoc_count + adjustments_count + 1),  # +1 for model
    }


def purge_model_hard(db: Session, model_id: int) -> dict[str, Decimal | int | str]:
    """Transactionally remove a model and all related rows, avoiding orphans.

    Returns the same summary as get_model_purge_impact.
    """
    impact = get_model_purge_impact(db, model_id)

    # Perform deletes in a transaction
    try:
        # Delete payouts and validations that reference this model (FK is SET NULL otherwise)
        db.query(Payout).filter(Payout.model_id == model_id).delete(synchronize_session=False)
        db.query(ValidationIssue).filter(ValidationIssue.model_id == model_id).delete(synchronize_session=False)

        # Delete associated adhoc payments and adjustments (FKs are CASCADE, but do explicitly for SQLite)
        db.query(AdhocPayment).filter(AdhocPayment.model_id == model_id).delete(synchronize_session=False)
        db.query(ModelCompensationAdjustment).filter(ModelCompensationAdjustment.model_id == model_id).delete(synchronize_session=False)

        # Finally delete the model
        model = get_model(db, model_id)
        if model:
            db.delete(model)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return impact


# --- Maintenance and audit helpers ----------------------------------------

def log_admin_action(db: Session, user_id: int | None, action: str, details: dict | None = None) -> None:
    payload = AuditLog(
        user_id=user_id,
        action=action,
        details=json.dumps(details or {}),
    )
    db.add(payload)
    db.commit()


def cleanup_empty_runs(db: Session) -> dict[str, int | list[int]]:
    """Delete schedule runs that have zero payouts. Returns count and ids."""
    runs = db.execute(select(ScheduleRun.id)).scalars().all()
    deleted_ids: list[int] = []
    for run_id in runs:
        count = db.execute(
            select(func.count()).where(Payout.schedule_run_id == run_id)
        ).scalar_one() or 0
        if count == 0:
            run = get_schedule_run(db, run_id)
            if run:
                db.delete(run)
                deleted_ids.append(run_id)
    if deleted_ids:
        db.commit()
    return {"deleted_runs": len(deleted_ids), "run_ids": deleted_ids}


def cleanup_orphans(db: Session) -> dict[str, int]:
    """Remove legacy orphan records where model_id is NULL.

    Payouts with model_id NULL are deleted. ValidationIssues with model_id NULL are deleted.
    """
    deleted_payouts = db.query(Payout).filter(Payout.model_id.is_(None)).delete(synchronize_session=False)
    deleted_validations = (
        db.query(ValidationIssue).filter(ValidationIssue.model_id.is_(None)).delete(synchronize_session=False)
    )
    if deleted_payouts or deleted_validations:
        db.commit()
    return {"payouts": int(deleted_payouts or 0), "validations": int(deleted_validations or 0)}


# --- Cash Advances CRUD ----------------------------------------------------

def list_advances_for_model(db: Session, model_id: int, status: str | None = None) -> Sequence[ModelAdvance]:
    stmt = select(ModelAdvance).where(ModelAdvance.model_id == model_id)
    if status:
        stmt = stmt.where(ModelAdvance.status == status)
    stmt = stmt.order_by(ModelAdvance.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_advance(db: Session, advance_id: int) -> ModelAdvance | None:
    return db.get(ModelAdvance, advance_id)


def outstanding_advance_total(db: Session, model_id: int) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(ModelAdvance.amount_remaining), 0))
        .where(ModelAdvance.model_id == model_id)
        .where(ModelAdvance.status.in_(["approved", "active"]))
    )
    value = db.execute(stmt).scalar_one() or 0
    return Decimal(value)


def create_advance(
    db: Session,
    model: Model,
    *,
    amount_total: Decimal,
    strategy: str = "fixed",
    fixed_amount: Decimal | None = None,
    percent_rate: Decimal | None = None,
    min_net_floor: Decimal | None = None,
    max_per_run: Decimal | None = None,
    cap_multiplier: Decimal | None = None,
    notes: str | None = None,
) -> ModelAdvance:
    strategy_value = (strategy or "fixed").lower()
    if strategy_value not in {"fixed", "percent"}:
        raise ValueError("strategy must be 'fixed' or 'percent'")

    if strategy_value == "fixed":
        if not fixed_amount or fixed_amount <= 0:
            raise ValueError("fixed_amount must be > 0 for fixed strategy")
    else:
        if percent_rate is None or percent_rate <= 0 or percent_rate > 100:
            raise ValueError("percent_rate must be in (0, 100] for percent strategy")

    advance = ModelAdvance(
        model_id=model.id,
        amount_total=amount_total,
        amount_remaining=amount_total,
        status="requested",
        strategy=strategy_value,
        fixed_amount=fixed_amount if strategy_value == "fixed" else None,
        percent_rate=percent_rate if strategy_value == "percent" else None,
        min_net_floor=(min_net_floor if min_net_floor is not None else ADVANCE_DEFAULT_MIN_FLOOR),
        max_per_run=(max_per_run if max_per_run is not None else ADVANCE_DEFAULT_MAX_PER_RUN),
        cap_multiplier=(cap_multiplier if cap_multiplier is not None else ADVANCE_DEFAULT_CAP_MULTIPLIER),
        notes=(notes.strip() if notes else None),
    )
    db.add(advance)
    db.commit()
    db.refresh(advance)
    return advance


def approve_advance(db: Session, advance: ModelAdvance, *, activate: bool = True) -> ModelAdvance:
    model = get_model(db, advance.model_id)
    if not model:
        raise ValueError("Model not found")
    # Cap enforcement removed per simplified policy

    advance.status = "active" if activate else "approved"
    if activate:
        advance.activated_at = datetime.now()
    db.add(advance)
    db.commit()
    db.refresh(advance)
    return advance


def close_advance_if_settled(db: Session, advance: ModelAdvance) -> None:
    if Decimal(advance.amount_remaining or 0) <= 0 and advance.status != "closed":
        advance.amount_remaining = Decimal("0")
        advance.status = "closed"
        db.add(advance)


def record_advance_repayment(
    db: Session,
    advance: ModelAdvance,
    *,
    amount: Decimal,
    source: str = "manual",
    payout: Payout | None = None,
) -> AdvanceRepayment:
    if amount <= 0:
        raise ValueError("Repayment amount must be > 0")
    applied = min(amount, Decimal(advance.amount_remaining or 0))
    repayment = AdvanceRepayment(
        advance_id=advance.id,
        payout_id=(payout.id if payout else None),
        amount=applied,
        source=("auto" if source == "auto" else "manual"),
    )
    advance.amount_remaining = Decimal(advance.amount_remaining or 0) - applied
    close_advance_if_settled(db, advance)
    db.add(advance)
    db.add(repayment)
    db.commit()
    db.refresh(repayment)
    return repayment


def _apply_advance_allocations_for_run(db: Session, run: ScheduleRun, payouts: list[Payout]) -> None:
    """Plan allocations for active advances and reduce payout amounts (net) accordingly.

    Creates PayoutAdvanceAllocation rows for this run and adjusts payout.amount.
    Does not modify advance balances. Idempotent per clear_schedule_data (we purge allocations on refresh).
    """
    # Group payouts by model, sort by pay_date to apply sequentially
    by_model: dict[int, list[Payout]] = {}
    for p in payouts:
        if not p.model_id:
            continue
        by_model.setdefault(p.model_id, []).append(p)
    for model_id, rows in by_model.items():
        rows.sort(key=lambda x: (x.pay_date, x.id))
        # Fetch active advances
        advances: list[ModelAdvance] = (
            db.execute(
                select(ModelAdvance).where(
                    ModelAdvance.model_id == model_id,
                    ModelAdvance.status == "active",
                ).order_by(ModelAdvance.created_at.asc())
            ).scalars().all()
        )
        if not advances:
            continue
        # Track a local temp remaining per advance for this run's planning
        temp_remaining: dict[int, Decimal] = {adv.id: Decimal(adv.amount_remaining or 0) for adv in advances}

        for payout in rows:
            # Available to deduct is the full payout amount (no floor)
            available = Decimal(payout.amount or 0)
            if available <= 0:
                continue
            total_deducted = Decimal("0")

            for adv in advances:
                if temp_remaining[adv.id] <= 0:
                    continue
                # Strategy amount
                if (adv.strategy or "fixed") == "fixed":
                    candidate = Decimal(adv.fixed_amount or 0)
                else:
                    # percent of gross payout amount
                    pct = Decimal(adv.percent_rate or 0) / Decimal("100")
                    candidate = (Decimal(payout.amount or 0) * pct)
                # Respect remaining room on this payout and advance balance
                remaining_room = max(available - total_deducted, Decimal("0"))
                planned = min(candidate, temp_remaining[adv.id], remaining_room)
                # Ensure non-negative and meaningful
                if planned <= 0:
                    continue

                # Reduce payout amount and temp remaining
                payout.amount = (Decimal(payout.amount or 0) - planned)
                total_deducted += planned
                temp_remaining[adv.id] = temp_remaining[adv.id] - planned

                # Create allocation row
                alloc = PayoutAdvanceAllocation(
                    schedule_run_id=run.id,
                    payout_id=payout.id,
                    model_id=model_id,
                    advance_id=adv.id,
                    planned_amount=planned,
                )
                db.add(alloc)

                # Stop if no more room on this payout
                if (available - total_deducted) <= 0:
                    break

        # Persist adjustments for this model's payouts before next model
        db.flush()


def delete_advance(db: Session, advance: ModelAdvance) -> None:
    """Delete an advance if it has no repayments; also remove any planned allocations."""
    # Prevent deletion if there are repayments recorded
    has_repayments = db.execute(
        select(func.count()).select_from(AdvanceRepayment).where(AdvanceRepayment.advance_id == advance.id)
    ).scalar_one() or 0
    if int(has_repayments) > 0:
        raise ValueError("Cannot delete an advance that has repayments.")

    # Delete any planned allocations for this advance
    db.query(PayoutAdvanceAllocation).filter(PayoutAdvanceAllocation.advance_id == advance.id).delete(synchronize_session=False)
    db.delete(advance)
    db.commit()


def _realize_allocations_for_paid_payout(db: Session, payout: Payout) -> None:
    allocations = db.execute(
        select(PayoutAdvanceAllocation).where(PayoutAdvanceAllocation.payout_id == payout.id)
    ).scalars().all()
    if not allocations:
        return
    # If repayments already exist for this payout, skip (idempotent)
    existing = db.execute(
        select(AdvanceRepayment).where(AdvanceRepayment.payout_id == payout.id)
    ).scalars().first()
    if existing:
        return

    for alloc in allocations:
        adv = get_advance(db, alloc.advance_id)
        if not adv:
            continue
        record_advance_repayment(db, adv, amount=Decimal(alloc.planned_amount or 0), source="auto", payout=payout)
        # Allocation will be deleted by cascade when clearing runs is not guaranteed, so delete explicitly on realize
        db.delete(alloc)
    db.flush()


# --- Export helpers for advances ------------------------------------------

def get_allocation_totals_for_run(db: Session, run_id: int) -> dict[int, Decimal]:
    """Return a mapping of payout_id -> total planned allocation for the run."""
    stmt = (
        select(PayoutAdvanceAllocation.payout_id, func.coalesce(func.sum(PayoutAdvanceAllocation.planned_amount), 0))
        .where(PayoutAdvanceAllocation.schedule_run_id == run_id)
        .group_by(PayoutAdvanceAllocation.payout_id)
    )
    out: dict[int, Decimal] = {}
    for payout_id, total in db.execute(stmt).all():
        out[int(payout_id)] = Decimal(total or 0)
    return out


def list_payouts_with_allocations_for_run(db: Session, run_id: int) -> Sequence[tuple[Payout, Decimal]]:
    """List payouts for a run and include the allocated amount for each payout (if any)."""
    allocations = get_allocation_totals_for_run(db, run_id)
    payouts = list_payouts_for_run(db, run_id)
    results: list[tuple[Payout, Decimal]] = []
    for p in payouts:
        results.append((p, allocations.get(p.id, Decimal("0"))))
    return results
