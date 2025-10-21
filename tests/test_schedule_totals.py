from datetime import date
from decimal import Decimal

from app.database import SessionLocal
from app.models import Model, Payout, ScheduleRun
from app.routers.schedules import _gather_dashboard_data
from app import crud


def _create_model(session, code: str, amount: str = "100.00") -> Model:
    model = Model(
        status="Active",
        code=code,
        real_name=f"Model {code}",
        working_name=f"Model {code}",
        start_date=date(2024, 1, 1),
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount_monthly=Decimal(amount),
    )
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def _create_run(session, year: int, month: int, total: str = "0") -> ScheduleRun:
    run = ScheduleRun(
        target_year=year,
        target_month=month,
        currency="USD",
        include_inactive=False,
        summary_models_paid=0,
        summary_total_payout=Decimal(total),
        summary_frequency_counts="{}",
        export_path="exports",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _create_payout(
    session,
    run: ScheduleRun,
    model: Model | None,
    amount: str,
    status: str = "not_paid",
) -> Payout:
    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id if model else None,
        pay_date=date(run.target_year, run.target_month, 25),
        code=model.code if model else "ORPHAN",
        real_name=(model.real_name if model else "Orphaned Model"),
        working_name=(model.working_name if model else "Orphaned Model"),
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount=Decimal(amount),
        notes=None,
        status=status,
    )
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return payout


def test_run_payment_summary_excludes_payouts_without_models():
    session = SessionLocal()
    try:
        year = 2025
        month = 10
        model_active = _create_model(session, "ACTIVE1", "100.00")
        model_deleted = _create_model(session, "DELETED1", "200.00")
        run = _create_run(session, year, month, total="300.00")

        _create_payout(session, run, model_active, "100.00")
        orphan = _create_payout(session, run, model_deleted, "200.00")

        orphan.model_id = None
        session.add(orphan)
        session.commit()

        summary = crud.run_payment_summary(session, run.id)
        assert summary["total_payout"] == Decimal("100.00")
        assert summary["unpaid_total"] == Decimal("100.00")
        assert summary["paid_total"] == Decimal("0")
    finally:
        session.close()


def test_dashboard_totals_ignore_deleted_models():
    session = SessionLocal()
    try:
        year = 2025
        month = 11
        model_active = _create_model(session, "ACTIVE2", "100.00")
        model_deleted = _create_model(session, "DELETED2", "150.00")
        run = _create_run(session, year, month, total="250.00")

        _create_payout(session, run, model_active, "100.00")
        orphan = _create_payout(session, run, model_deleted, "150.00")

        orphan.model_id = None
        session.add(orphan)
        session.commit()

        month_slug = f"{year:04d}-{month:02d}"
        dashboard = _gather_dashboard_data(session, month_slug)

        assert dashboard["monthly_summary"]["total_payout"] == Decimal("100.00")
        assert dashboard["monthly_summary"]["paid_total"] == Decimal("0")
        assert dashboard["monthly_summary"]["unpaid_total"] == Decimal("100.00")
        assert dashboard["selected_run_cards"][0]["total"] == Decimal("100.00")
        assert dashboard["selected_runs"][0].summary_total_payout == Decimal("100.00")
    finally:
        session.close()
