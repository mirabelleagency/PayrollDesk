"""Tests for signed session security and API auth isolation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.keys import create_api_key_record
from app.env_config import validate_api_secrets_at_startup
from app.main import app


def test_forged_user_id_cookie_does_not_authenticate():
    """Legacy unsigned user_id cookies must not grant access."""
    client = TestClient(app)
    client.cookies.set("user_id", "1")
    resp = client.get("/dashboard", headers={"accept": "application/json"}, follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_session_cookie_alone_does_not_access_api_v2(test_db):
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    resp = client.get("/api/v2/snapshot")
    assert resp.status_code == 401


def test_api_key_alone_does_not_access_admin_api_keys(test_db):
    _, plaintext = create_api_key_record(
        test_db,
        name="integration",
        created_by="admin",
        scopes=["v2:*"],
    )
    test_db.commit()
    client = TestClient(app)
    resp = client.get("/admin/api-keys", headers={"X-API-Key": plaintext}, follow_redirects=False)
    assert resp.status_code in (303, 307, 401)


def test_production_requires_api_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("API_RATE_SECRET", raising=False)
    monkeypatch.delenv("API_CURSOR_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="API_RATE_SECRET"):
        validate_api_secrets_at_startup()
