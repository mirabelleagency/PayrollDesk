from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Model, ScheduleRun, Payout


def seed_overdue(session, days_ago: int = 1, code: str = "MOD1") -> tuple[ScheduleRun, Payout]:
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
        code=code,
        real_name=f"Real {code}",
        working_name=f"Model {code}",
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
        pay_date=today - timedelta(days=days_ago),
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


def test_overdue_consolidated_list_includes_all_runs():
    session = SessionLocal()
    try:
        # Seed two different overdue payouts across separate runs
        seed_overdue(session, days_ago=3, code="A001")
        seed_overdue(session, days_ago=5, code="B002")
    finally:
        session.close()

    client = TestClient(app)
    login_admin(client)

    resp = client.get("/schedules?show=overdue")
    assert resp.status_code == 200
    text = resp.text
    # Both codes should appear in the consolidated overdue table
    assert "A001" in text
    assert "B002" in text


def test_dashboard_overdue_review_links_to_current_month_view():
    session = SessionLocal()
    try:
        seed_overdue(session, days_ago=2, code="R123")
    finally:
        session.close()

    client = TestClient(app)
    login_admin(client)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    # The dashboard Review button should now link directly to the current month cycle with overdue filter
    import re
    match = re.search(r"/schedules/(\d+)\?show=overdue#payments-overdue", resp.text)
    assert match, "Expected Review link to point to current month cycle with overdue filter"
