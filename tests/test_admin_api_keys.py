"""Tests for admin API key management."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.api.keys import hash_api_key, list_api_keys
from app.main import app
from app.models import ApiKey, AuditLog


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _login_admin(client: TestClient) -> None:
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_admin_api_keys_requires_login(client):
    resp = client.get("/admin/api-keys", follow_redirects=False)
    assert resp.status_code in (303, 307)
    assert "/login" in resp.headers.get("location", "")


def test_admin_create_and_revoke_api_key(client, test_db):
    _login_admin(client)
    page = client.get("/admin/api-keys")
    assert page.status_code == 200
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert csrf_match
    csrf_token = csrf_match.group(1)
    nonce_match = re.search(r'name="form_nonce" value="([^"]+)"', page.text)
    assert nonce_match
    form_nonce = nonce_match.group(1)

    create = client.post(
        "/admin/api-keys",
        data={"name": "Partner sync", "csrf_token": csrf_token, "form_nonce": form_nonce, "scopes": "v1:*"},
    )
    assert create.status_code == 200
    assert create.headers.get("cache-control") == "no-store"
    assert "pd_" in create.text

    keys = list_api_keys(test_db)
    assert len(keys) == 1
    assert keys[0].name == "Partner sync"
    assert keys[0].key_hash != ""
    assert not any(keys[0].key_hash == hash_api_key(token) for token in ["pd_fake"])

    audit = test_db.query(AuditLog).filter(AuditLog.action == "create_api_key").first()
    assert audit is not None

    page2 = client.get("/admin/api-keys")
    csrf_token2 = re.search(r'name="csrf_token" value="([^"]+)"', page2.text).group(1)
    revoke_nonce_match = re.search(
        rf'action="/admin/api-keys/{keys[0].id}/revoke"[\s\S]*?name="form_nonce" value="([^"]+)"',
        page2.text,
    )
    assert revoke_nonce_match
    revoke = client.post(
        f"/admin/api-keys/{keys[0].id}/revoke",
        data={"csrf_token": csrf_token2, "form_nonce": revoke_nonce_match.group(1)},
        follow_redirects=False,
    )
    assert revoke.status_code == 303
    test_db.refresh(keys[0])
    assert keys[0].revoked_at is not None

    revoke_audit = test_db.query(AuditLog).filter(AuditLog.action == "revoke_api_key").first()
    assert revoke_audit is not None


def test_plaintext_key_not_stored(client, test_db):
    _login_admin(client)
    page = client.get("/admin/api-keys")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    form_nonce = re.search(r'name="form_nonce" value="([^"]+)"', page.text).group(1)
    create = client.post(
        "/admin/api-keys",
        data={"name": "Once", "csrf_token": csrf_token, "form_nonce": form_nonce, "scopes": "v1:*"},
    )
    key_match = re.search(r'<pre id="new-api-key"[^>]*>(pd_[^<]+)</pre>', create.text)
    assert key_match
    plaintext = key_match.group(1).strip()
    stored = test_db.query(ApiKey).one()
    assert stored.key_hash == hash_api_key(plaintext)
    assert plaintext not in stored.key_hash
