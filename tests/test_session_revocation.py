"""Logging out or changing a password ends existing sessions."""
from fastapi.testclient import TestClient

from app.auth import User
from app.database import SessionLocal
from app.main import app
from app.routers.auth import _signer
from conftest import csrf_token_for

PROTECTED = "/profile/"


def _make_user(username: str, password: str) -> int:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            user = User.create_user(username, password, role="user")
            session.add(user)
        else:
            user.password_hash = User.hash_password(password)
            user.session_version = 0
        session.commit()
        return user.id
    finally:
        session.close()


def _login(username: str, password: str) -> TestClient:
    client = TestClient(app)
    resp = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert resp.status_code == 303
    return client


def _authenticated(client: TestClient) -> bool:
    resp = client.get(PROTECTED, headers={"Accept": "application/json"}, follow_redirects=False)
    return resp.status_code == 200


def test_logout_ends_a_copied_cookie():
    _make_user("revoke1", "Revoke-password-123")
    browser = _login("revoke1", "Revoke-password-123")
    copy = TestClient(app)
    copy.cookies.set("session", browser.cookies.get("session"))
    assert _authenticated(copy)

    browser.get("/logout", follow_redirects=False)

    # Before: the copied cookie stayed valid for up to 24h after logout.
    assert not _authenticated(copy)


def test_password_change_keeps_this_browser_and_ends_the_others():
    _make_user("revoke2", "Revoke-password-123")
    here = _login("revoke2", "Revoke-password-123")
    elsewhere = _login("revoke2", "Revoke-password-123")

    token = csrf_token_for(here)
    resp = here.post(
        "/profile/change-password",
        data={
            "current_password": "Revoke-password-123",
            "new_password": "New-revoke-password-456",
            "confirm_password": "New-revoke-password-456",
            "_csrf_token": token,
        },
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 200
    assert "Password changed successfully" in resp.text

    assert _authenticated(here)
    assert not _authenticated(elsewhere)


def test_admin_reset_ends_the_users_sessions():
    user_id = _make_user("revoke3", "Revoke-password-123")
    victim = _login("revoke3", "Revoke-password-123")
    admin = _login("admin", "admin")
    token = csrf_token_for(admin)
    resp = admin.post(
        f"/admin/users/{user_id}/reset-password",
        data={"new_password": "Reset-password-789", "_csrf_token": token},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert not _authenticated(victim)


def test_cookie_from_before_this_change_still_works_until_revoked():
    user_id = _make_user("revoke4", "Revoke-password-123")
    legacy = TestClient(app)
    legacy.cookies.set("session", _signer.dumps(user_id))  # old format: bare user id
    assert _authenticated(legacy)

    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        user.end_all_sessions()
        session.commit()
    finally:
        session.close()
    assert not _authenticated(legacy)
