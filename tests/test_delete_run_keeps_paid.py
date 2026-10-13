"""A run containing paid payouts can't be deleted."""
from fastapi.testclient import TestClient

from app import crud
from app.database import SessionLocal
from app.main import app
from app.models import Payout, ScheduleRun
from conftest import csrf_token_for
from tests.test_payout_notes import seed_run_with_payout


def _delete(run_id: int):
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    token = csrf_token_for(client)
    return client.post(
        f"/schedules/{run_id}/delete",
        data={"_csrf_token": token},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
        follow_redirects=False,
    )


def test_run_with_a_paid_payout_is_kept():
    session = SessionLocal()
    try:
        run, payout = seed_run_with_payout(session)
        crud.update_payout(session, payout, None, "paid")
        run_id, payout_id = run.id, payout.id
    finally:
        session.close()

    resp = _delete(run_id)
    # Before: 303 and the paid payout was gone.
    assert resp.status_code == 409
    assert "paid payout" in resp.json()["detail"]

    session = SessionLocal()
    try:
        assert session.get(ScheduleRun, run_id) is not None
        assert session.get(Payout, payout_id).status == "paid"
    finally:
        session.close()


def test_run_with_only_unpaid_payouts_can_be_deleted():
    session = SessionLocal()
    try:
        run, _ = seed_run_with_payout(session)
        run_id = run.id
    finally:
        session.close()

    assert _delete(run_id).status_code == 303
    session = SessionLocal()
    try:
        assert session.get(ScheduleRun, run_id) is None
    finally:
        session.close()
