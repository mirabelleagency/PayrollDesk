"""Bulk exports (legal names, wallets, pay data) are admin-only."""
import pytest
from fastapi.testclient import TestClient

from app.auth import User
from app.database import SessionLocal
from app.main import app
from conftest import csrf_token_for
from tests.test_payout_notes import seed_run_with_payout

GET_EXPORTS = ["/dashboard/export", "/dashboard/export-xlsx", "/models/export", "/schedules/all-table/export"]
POST_EXPORTS = ["/models/export", "/schedules/export"]


def _login(client: TestClient, username: str, password: str) -> None:
    resp = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert resp.status_code in (303, 307)


@pytest.fixture()
def clerk_client():
    session = SessionLocal()
    try:
        if not session.query(User).filter(User.username == "clerk").first():
            session.add(User.create_user("clerk", "Clerk-password-123", role="user"))
            session.commit()
    finally:
        session.close()
    client = TestClient(app)
    _login(client, "clerk", "Clerk-password-123")
    return client


@pytest.mark.parametrize("path", GET_EXPORTS)
def test_non_admin_cannot_download_exports(clerk_client, path):
    resp = clerk_client.get(path, headers={"Accept": "application/json"})
    assert resp.status_code == 403


@pytest.mark.parametrize("path", POST_EXPORTS)
def test_non_admin_cannot_post_exports(clerk_client, path):
    token = csrf_token_for(clerk_client)
    resp = clerk_client.post(
        path,
        data={"_csrf_token": token},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )
    assert resp.status_code == 403


def test_non_admin_cannot_download_a_run_schedule(clerk_client):
    session = SessionLocal()
    try:
        run, _ = seed_run_with_payout(session)
        run_id = run.id
    finally:
        session.close()
    resp = clerk_client.get(f"/schedules/{run_id}/download/csv", headers={"Accept": "application/json"})
    assert resp.status_code == 403


@pytest.mark.parametrize("path", GET_EXPORTS)
def test_admin_can_still_download_exports(path):
    client = TestClient(app)
    _login(client, "admin", "admin")
    resp = client.get(path)
    assert resp.status_code == 200
