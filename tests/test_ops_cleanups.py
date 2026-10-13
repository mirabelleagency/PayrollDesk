"""Orphan cleanup keeps paid history and doesn't 500; /health/db hides errors."""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal, get_session
from app.main import app
from app.models import Payout
from conftest import csrf_token_for
from tests.test_payout_notes import seed_run_with_payout


def test_cleanup_orphans_keeps_paid_and_redirects():
    session = SessionLocal()
    try:
        run, unpaid = seed_run_with_payout(session)
        paid = Payout(
            schedule_run_id=run.id, model_id=None, pay_date=date(2026, 1, 15), code="GONE",
            real_name="R", working_name="W", payment_method="Wire", payment_frequency="monthly",
            amount=Decimal("75.00"), status="paid", is_locked=True,
        )
        session.add(paid)
        unpaid.model_id = None
        session.commit()
        paid_id, unpaid_id = paid.id, unpaid.id
    finally:
        session.close()

    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    token = csrf_token_for(client)
    resp = client.post(
        "/admin/maintenance/cleanup-orphans",
        data={"_csrf_token": token},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    # Before: 500 (NameError: msg) after the cleanup had already committed.
    assert resp.status_code == 303
    assert "Cleanup+complete" in resp.headers["location"]

    session = SessionLocal()
    try:
        assert session.get(Payout, unpaid_id) is None
        # Before: the paid orphan was deleted too.
        assert session.get(Payout, paid_id) is not None
    finally:
        session.close()


def test_health_db_does_not_leak_the_error():
    class Broken:
        def execute(self, *args, **kwargs):
            raise RuntimeError("could not connect to db-internal.secret-host:5432 as payroll")

    app.dependency_overrides[get_session] = lambda: Broken()
    try:
        resp = TestClient(app).get("/health/db")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert resp.status_code == 503
    assert "secret-host" not in resp.text
    assert resp.json()["database"]["error"] == "database unavailable"
