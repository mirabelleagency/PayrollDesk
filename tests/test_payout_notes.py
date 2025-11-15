from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Model, ScheduleRun, Payout


def seed_run_with_payout(session) -> tuple[ScheduleRun, Payout]:
    today = date.today()
    run = ScheduleRun(
        target_year=today.year,
        target_month=today.month,
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

    model = Model(
        status="Active",
        code="NOTE1",
        real_name="Real NOTE1",
        working_name="Model NOTE1",
        start_date=today.replace(day=1),
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount_monthly=Decimal("100.00"),
    )
    session.add(model)
    session.commit()
    session.refresh(model)

    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id,
        pay_date=today,
        code=model.code,
        real_name=model.real_name,
        working_name=model.working_name,
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount=Decimal("50.00"),
        status="not_paid",
    )
    session.add(payout)
    session.commit()
    session.refresh(payout)
    return run, payout


def login_admin(client: TestClient) -> None:
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)


def test_notes_update_returns_json_and_persists():
    session = SessionLocal()
    try:
        run, payout = seed_run_with_payout(session)
        run_id = run.id
        payout_id = payout.id
    finally:
        session.close()

    client = TestClient(app)
    login_admin(client)

    payload = {
        "notes": "Needs invoice #55",
        "status": "approved",
        "redirect_to": f"/schedules/{run_id}",
    }

    resp = client.post(
        f"/schedules/{run_id}/payouts/{payout_id}/note",
        data=payload,
        headers={"X-Requested-With": "fetch"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["note"] == payload["notes"]
    assert data["status"] == "approved"
    assert isinstance(data["is_overdue"], bool)

    session = SessionLocal()
    try:
        refreshed = session.get(Payout, payout_id)
        assert refreshed is not None
        assert refreshed.notes == payload["notes"]
        assert refreshed.status == "approved"
    finally:
        session.close()
