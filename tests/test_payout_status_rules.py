"""Who may change a payout's status, and which changes are allowed."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import crud
from app.auth import User
from app.database import SessionLocal
from app.main import app
from app.models import (
    AdvanceRepayment,
    ModelAdvance,
    Payout,
    PayoutAdvanceAllocation,
)
from conftest import csrf_token_for
from tests.test_payout_notes import seed_run_with_payout


def _login(client: TestClient, username: str, password: str) -> None:
    resp = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert resp.status_code in (303, 307)


@pytest.fixture()
def seeded():
    session = SessionLocal()
    try:
        run, payout = seed_run_with_payout(session)
        yield run.id, payout.id, payout.model_id
    finally:
        session.close()


@pytest.fixture()
def non_admin_user():
    session = SessionLocal()
    try:
        if not session.query(User).filter(User.username == "clerk").first():
            session.add(User.create_user("clerk", "Clerk-password-123", role="user"))
            session.commit()
    finally:
        session.close()
    return "clerk", "Clerk-password-123"


def _payout(payout_id: int) -> Payout:
    session = SessionLocal()
    try:
        return session.get(Payout, payout_id)
    finally:
        session.close()


def _post_status(client: TestClient, run_id: int, payout_id: int, status: str):
    return client.post(
        f"/schedules/{run_id}/payouts/{payout_id}/status",
        data={"status": status, "_csrf_token": csrf_token_for(client)},
        headers={"X-CSRF-Token": csrf_token_for(client), "Accept": "application/json"},
    )


def test_non_admin_cannot_change_status(seeded, non_admin_user):
    run_id, payout_id, _ = seeded
    client = TestClient(app)
    _login(client, *non_admin_user)

    single = _post_status(client, run_id, payout_id, "paid")
    assert single.status_code == 403

    bulk = client.post(
        "/schedules/combined-payouts/bulk-status",
        data={"payout_ids": str(payout_id), "status": "paid", "_csrf_token": csrf_token_for(client)},
        headers={"X-CSRF-Token": csrf_token_for(client)},
    )
    assert bulk.status_code == 403
    assert _payout(payout_id).status == "not_paid"


def test_admin_marks_paid_and_can_correct_a_mistake(seeded):
    run_id, payout_id, _ = seeded
    client = TestClient(app)
    _login(client, "admin", "admin")

    assert _post_status(client, run_id, payout_id, "paid").status_code == 200
    paid = _payout(payout_id)
    assert paid.status == "paid" and paid.is_locked

    # No repayment was recorded, so reverting a mistaken "paid" is allowed and unlocks.
    assert _post_status(client, run_id, payout_id, "not_paid").status_code == 200
    reverted = _payout(payout_id)
    assert reverted.status == "not_paid" and not reverted.is_locked


def _paid_with_repayment(payout_id: int, model_id: int) -> None:
    session = SessionLocal()
    try:
        payout = session.get(Payout, payout_id)
        advance = ModelAdvance(
            model_id=model_id,
            amount_total=Decimal("100"),
            amount_remaining=Decimal("100"),
            status="active",
        )
        session.add(advance)
        session.flush()
        session.add(
            PayoutAdvanceAllocation(
                schedule_run_id=payout.schedule_run_id,
                payout_id=payout.id,
                model_id=model_id,
                advance_id=advance.id,
                planned_amount=Decimal("20"),
            )
        )
        session.commit()
        assert crud.update_payout(session, payout, None, "paid") == Decimal("20")
    finally:
        session.close()


def test_paid_payout_with_repayment_cannot_be_unpaid(seeded):
    run_id, payout_id, model_id = seeded
    _paid_with_repayment(payout_id, model_id)

    client = TestClient(app)
    _login(client, "admin", "admin")

    single = _post_status(client, run_id, payout_id, "not_paid")
    assert single.status_code == 409
    assert "repayment" in single.json()["detail"]

    bulk = client.post(
        f"/schedules/{run_id}/payouts/bulk-update/status",
        data={"payout_ids": str(payout_id), "status": "on_hold", "_csrf_token": csrf_token_for(client)},
        headers={"X-CSRF-Token": csrf_token_for(client)},
    )
    assert bulk.status_code == 200
    body = bulk.json()
    assert body["updated_ids"] == []
    assert body["skipped"][0]["id"] == payout_id

    still = _payout(payout_id)
    assert still.status == "paid" and still.is_locked


def test_failed_repayment_leaves_payout_unpaid(seeded):
    """Marking paid realizes allocations in the same transaction: if one fails,
    nothing sticks — not paid, not locked, no partial repayment."""
    _, payout_id, model_id = seeded
    session = SessionLocal()
    try:
        payout = session.get(Payout, payout_id)
        settled = ModelAdvance(
            model_id=model_id,
            amount_total=Decimal("50"),
            amount_remaining=Decimal("0"),  # already repaid elsewhere
            status="active",
        )
        session.add(settled)
        session.flush()
        session.add(
            PayoutAdvanceAllocation(
                schedule_run_id=payout.schedule_run_id,
                payout_id=payout.id,
                model_id=model_id,
                advance_id=settled.id,
                planned_amount=Decimal("20"),
            )
        )
        session.commit()

        with pytest.raises(ValueError):
            crud.update_payout(session, payout, None, "paid")
    finally:
        session.close()

    after = _payout(payout_id)
    assert after.status == "not_paid" and not after.is_locked
    check = SessionLocal()
    try:
        assert check.query(AdvanceRepayment).filter(AdvanceRepayment.payout_id == payout_id).count() == 0
    finally:
        check.close()


def test_unpaid_statuses_move_freely(seeded):
    _, payout_id, _ = seeded
    session = SessionLocal()
    try:
        payout = session.get(Payout, payout_id)
        for status in ("approved", "on_hold", "not_paid", "approved"):
            crud.update_payout(session, payout, None, status)
            assert payout.status == status and not payout.is_locked
        with pytest.raises(crud.PayoutStatusError):
            crud.update_payout(session, payout, None, "bogus")
    finally:
        session.close()
