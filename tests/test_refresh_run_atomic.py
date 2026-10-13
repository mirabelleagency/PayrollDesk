"""Refreshing a schedule run is all-or-nothing, and survives a renamed model code."""
from datetime import date
from decimal import Decimal

import pytest

from app import crud
from app.database import SessionLocal
from app.models import Model, Payout, ScheduleRun
from app.services import PayrollService


def _model(session, code: str) -> Model:
    model = Model(
        status="Active",
        code=code,
        real_name=f"Real {code}",
        working_name=f"Working {code}",
        start_date=date(2025, 1, 1),
        payment_method="Crypto",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000"),
    )
    session.add(model)
    session.commit()
    return model


def _run(session, tmp_path):
    return PayrollService(session).run_payroll(
        target_year=2026, target_month=10, currency="USD", include_inactive=False, output_dir=tmp_path
    )


def test_failed_refresh_leaves_the_run_as_it_was(tmp_path, monkeypatch):
    session = SessionLocal()
    try:
        _model(session, "ATOM1")
        *_, run_id = _run(session, tmp_path)
        before = sorted(
            (p.code, p.pay_date, p.amount) for p in session.query(Payout).filter_by(schedule_run_id=run_id)
        )
        assert before, "initial run should have payouts"

        def boom(*args, **kwargs):
            raise RuntimeError("simulated failure mid-refresh")

        monkeypatch.setattr(crud, "store_payouts", boom)
        with pytest.raises(RuntimeError):
            _run(session, tmp_path)

        session.expire_all()
        after = sorted(
            (p.code, p.pay_date, p.amount) for p in session.query(Payout).filter_by(schedule_run_id=run_id)
        )
        # Before: the unlocked payouts were already deleted and committed.
        assert after == before
    finally:
        session.close()


def test_refresh_after_renaming_a_code_keeps_the_locked_payout(tmp_path):
    session = SessionLocal()
    try:
        model = _model(session, "OLD1")
        *_, run_id = _run(session, tmp_path)
        payout = session.query(Payout).filter_by(schedule_run_id=run_id, model_id=model.id).one()
        crud.update_payout(session, payout, None, "paid")
        paid_id, paid_date = payout.id, payout.pay_date

        model.code = "NEW1"
        session.commit()

        # Before: the regenerated NEW1 payout collided with the locked OLD1 one
        # on (run, model, pay_date) and the refresh died half-way.
        _run(session, tmp_path)

        session.expire_all()
        rows = session.query(Payout).filter_by(schedule_run_id=run_id, model_id=model.id).all()
        assert [(p.id, p.status, p.is_locked) for p in rows if p.pay_date == paid_date] == [(paid_id, "paid", True)]
        assert session.query(ScheduleRun).count() == 1
    finally:
        session.close()
