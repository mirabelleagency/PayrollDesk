from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app import crud
from app.models import Model, ScheduleRun, Payout


def _make_basic_model(session):
    m = Model(
        status="Active",
        code="APPR1",
        real_name="Approved Tester",
        working_name="Approved Tester",
        start_date=date.today() - timedelta(days=30),
        payment_method="Bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def _make_run_with_payout(session, model: Model, pay_date: date):
    run = ScheduleRun(
        target_year=pay_date.year,
        target_month=pay_date.month,
        currency="USD",
        include_inactive=False,
        summary_models_paid=0,
        summary_total_payout=Decimal("0"),
        summary_frequency_counts="{}",
        export_path="exports",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id,
        pay_date=pay_date,
        code=model.code,
        real_name=model.real_name,
        working_name=model.working_name,
        payment_method=model.payment_method,
        payment_frequency=model.payment_frequency,
        amount=Decimal("100.00"),
        status="not_paid",
    )
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return run, payout


def login_admin(client: TestClient) -> None:
    # Reuse helper from other tests if available; inline minimal login
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)


def test_set_status_approved_and_unmark():
    session = SessionLocal()
    try:
        model = _make_basic_model(session)
        run, payout = _make_run_with_payout(session, model, date.today())
        client = TestClient(app)
        login_admin(client)

        # Set approved
        resp = client.post(f"/schedules/{run.id}/payouts/{payout.id}/status", data={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["new_status"] == "approved"
        assert data["is_overdue"] is False

        session.refresh(payout)
        assert payout.status == "approved"

        # Unmark approved back to not_paid
        resp2 = client.post(f"/schedules/{run.id}/payouts/{payout.id}/status", data={"status": "not_paid"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["new_status"] == "not_paid"

        session.refresh(payout)
        assert payout.status == "not_paid"
    finally:
        session.close()


def test_overdue_flag_excludes_approved():
    session = SessionLocal()
    try:
        model = _make_basic_model(session)
        past_date = date.today() - timedelta(days=10)
        run, payout = _make_run_with_payout(session, model, past_date)
        client = TestClient(app)
        login_admin(client)

        # Mark approved; should not be overdue according to server logic (only not_paid/on_hold)
        resp = client.post(f"/schedules/{run.id}/payouts/{payout.id}/status", data={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_status"] == "approved"
        assert data["is_overdue"] is False
    finally:
        session.close()
