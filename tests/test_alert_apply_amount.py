"""Applying a compensation alert gives the payout its share of the new monthly rate."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Model, Payout, PayoutCompensationAlert, ScheduleRun
from conftest import csrf_token_for


def _seed(frequency: str, payout_amount: str) -> tuple[int, int, int]:
    session = SessionLocal()
    try:
        model = Model(
            status="Active",
            code=f"ALR-{frequency}",
            real_name="Real",
            working_name="Working",
            start_date=date(2025, 1, 1),
            payment_method="Crypto",
            payment_frequency=frequency,
            amount_monthly=Decimal("4000"),
        )
        run = ScheduleRun(target_year=2026, target_month=10)
        session.add_all([model, run])
        session.flush()
        payout = Payout(
            schedule_run_id=run.id,
            model_id=model.id,
            pay_date=date(2026, 10, 31),
            code=model.code,
            real_name="Real",
            working_name="Working",
            payment_method="Crypto",
            # Generated schedules store the frequency title-cased.
            payment_frequency=frequency.title(),
            amount=Decimal(payout_amount),
            gross_amount=Decimal(payout_amount),
            status="not_paid",
        )
        session.add(payout)
        session.flush()
        alert = PayoutCompensationAlert(
            payout_id=payout.id,
            model_id=model.id,
            schedule_run_id=run.id,
            original_amount=Decimal(payout_amount),
            new_amount=Decimal("5000"),  # the new monthly rate
            effective_date=date(2026, 10, 1),
        )
        session.add(alert)
        session.commit()
        return run.id, payout.id, alert.id
    finally:
        session.close()


@pytest.mark.parametrize(
    "frequency, payout_amount, expected",
    [("weekly", "1000.00", "1250.00"), ("biweekly", "2000.00", "2500.00"), ("monthly", "4000.00", "5000.00")],
)
def test_apply_new_uses_the_payouts_share_of_the_monthly_rate(frequency, payout_amount, expected):
    run_id, payout_id, alert_id = _seed(frequency, payout_amount)
    client = TestClient(app)
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)

    resp = client.post(
        f"/schedules/{run_id}/compensation-alerts/{alert_id}/resolve",
        data={"action": "apply_new", "_csrf_token": csrf_token_for(client)},
        headers={"X-CSRF-Token": csrf_token_for(client), "Accept": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["amount_applied"] == float(expected)

    session = SessionLocal()
    try:
        payout = session.get(Payout, payout_id)
        # Before: every frequency got the full 5000.
        assert payout.amount == Decimal(expected)
        assert payout.gross_amount == Decimal(expected)
    finally:
        session.close()
