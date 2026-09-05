"""Tests for signed session security."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.session_config import get_session_secret


def test_forged_user_id_cookie_does_not_authenticate():
    """Legacy unsigned user_id cookies must not grant access."""
    client = TestClient(app)
    client.cookies.set("user_id", "1")
    resp = client.get("/dashboard", headers={"accept": "application/json"}, follow_redirects=False)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_production_requires_session_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_session_secret()


def test_staging_requires_session_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_session_secret()


def test_weak_session_secret_rejected_outside_dev(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SESSION_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="at least"):
        get_session_secret()
