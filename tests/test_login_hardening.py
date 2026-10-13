"""Login doesn't reveal which usernames exist; long passwords don't crash it;
admin-created users follow the password rules."""
from fastapi.testclient import TestClient

from app.auth import User
from app.database import SessionLocal
from app.main import app
from conftest import csrf_token_for


def _failed_login(username: str) -> str:
    client = TestClient(app)
    resp = client.post("/login", data={"username": username, "password": "wrong-password"}, follow_redirects=False)
    assert resp.status_code == 401
    return resp.text


def test_failed_login_message_is_the_same_for_real_and_unknown_users():
    session = SessionLocal()
    try:
        if not session.query(User).filter(User.username == "enum-real").first():
            session.add(User.create_user("enum-real", "Enum-password-123"))
            session.commit()
    finally:
        session.close()
    _failed_login("enum-real")  # one failure already on the real account
    real, unknown = _failed_login("enum-real"), _failed_login("enum-nobody")
    # Before: "(3 attempts remaining)" vs "(5 attempts remaining)".
    assert "remaining" not in real and "remaining" not in unknown
    assert "Invalid username or password" in real and "Invalid username or password" in unknown


def test_password_longer_than_72_bytes_does_not_crash():
    long_password = "Aa1!" + "x" * 100
    user = User.create_user("long-pass", long_password)
    assert user.verify_password(long_password)
    assert not user.verify_password("Aa1!" + "y" * 100)

    client = TestClient(app)
    resp = client.post("/login", data={"username": "nobody-long", "password": "z" * 200}, follow_redirects=False)
    assert resp.status_code == 401  # before: 500 (bcrypt 5 rejects > 72 bytes)


def test_admin_cannot_create_a_user_with_a_weak_password():
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    token = csrf_token_for(client)
    resp = client.post(
        "/admin/users/new",
        data={"username": "weakling", "password": "123", "role": "user", "_csrf_token": token},
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 400
    session = SessionLocal()
    try:
        assert session.query(User).filter(User.username == "weakling").first() is None
    finally:
        session.close()
