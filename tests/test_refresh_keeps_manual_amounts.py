"""Refreshing a run keeps payout amounts an admin chose."""
from datetime import date
from decimal import Decimal

from app import crud
from app.database import SessionLocal
from app.models import Model, Payout, PayoutCompensationAlert
from app.services import PayrollService


def _run(session, tmp_path):
    return PayrollService(session).run_payroll(
        target_year=2026, target_month=10, currency="USD", include_inactive=False, output_dir=tmp_path
    )


def test_applied_alert_amount_survives_refresh(tmp_path):
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code="KEEP1", real_name="Real", working_name="Working",
            start_date=date(2025, 1, 1), payment_method="Crypto", payment_frequency="monthly",
            amount_monthly=Decimal("1000"),
        )
        other = Model(
            status="Active", code="KEEP2", real_name="Real2", working_name="Working2",
            start_date=date(2025, 1, 1), payment_method="Crypto", payment_frequency="monthly",
            amount_monthly=Decimal("800"),
        )
        session.add_all([model, other])
        session.commit()
        *_, run_id = _run(session, tmp_path)

        payout = session.query(Payout).filter_by(schedule_run_id=run_id, model_id=model.id).one()
        alert = PayoutCompensationAlert(
            payout_id=payout.id, model_id=model.id, schedule_run_id=run_id,
            original_amount=Decimal("1000"), new_amount=Decimal("1300"), effective_date=date(2026, 10, 15),
        )
        session.add(alert)
        session.commit()
        crud.apply_alert_to_payout(session, alert, Decimal("1150.00"), resolved_by="admin")  # prorated
        session.commit()

        # A rate change elsewhere triggers a refresh of the run.
        other.amount_monthly = Decimal("900")
        session.commit()
        _run(session, tmp_path)

        session.expire_all()
        kept = session.query(Payout).filter_by(schedule_run_id=run_id, model_id=model.id).one()
        # Before: refresh regenerated it at the model's rate, 1000.
        assert kept.amount == Decimal("1150.00")
        assert kept.gross_amount == Decimal("1150.00")
        assert kept.amount_overridden

        recalculated = session.query(Payout).filter_by(schedule_run_id=run_id, model_id=other.id).one()
        assert recalculated.amount == Decimal("900.00")
        assert not recalculated.amount_overridden
    finally:
        session.close()
