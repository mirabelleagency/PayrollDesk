"""Tests for admin API key management."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.api.keys import hash_api_key, list_api_keys
from app.main import app
from app.models import ApiKey, AuditLog
from conftest import csrf_token_for


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
    csrf_token = csrf_token_for(client)

    create = client.post(
        "/admin/api-keys",
        data={"name": "Partner sync", "_csrf_token": csrf_token, "scopes": "v2:*"},
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
    csrf_token2 = csrf_token_for(client)
    revoke = client.post(
        f"/admin/api-keys/{keys[0].id}/revoke",
        data={"_csrf_token": csrf_token2},
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
    csrf_token = csrf_token_for(client)
    create = client.post(
        "/admin/api-keys",
        data={"name": "Once", "_csrf_token": csrf_token, "scopes": "v2:*"},
    )
    key_match = re.search(r'<pre id="new-api-key"[^>]*>(pd_[^<]+)</pre>', create.text)
    assert key_match
    plaintext = key_match.group(1).strip()
    stored = test_db.query(ApiKey).one()
    assert stored.key_hash == hash_api_key(plaintext)
    assert plaintext not in stored.key_hash


def _create(client, **data):
    client.get("/admin/api-keys")
    return client.post("/admin/api-keys", data={"_csrf_token": csrf_token_for(client), **data})


def test_create_form_offers_only_v2(client):
    _login_admin(client)
    page = client.get("/admin/api-keys")
    assert 'value="v2:payouts"' in page.text
    assert 'value="v1:' not in page.text


def test_new_keys_cannot_be_given_v1_scopes(client, test_db):
    _login_admin(client)
    resp = _create(client, name="Old style", preset="custom", scopes="v1:*")
    assert "v1 API has been removed" in resp.text
    assert 'value="Old style"' in resp.text  # the form keeps what was typed
    assert test_db.query(ApiKey).count() == 0


def test_salary_preset_grants_only_what_the_salary_sync_reads(client, test_db):
    _login_admin(client)
    _create(client, name="Miranance", preset="salary", scopes="v2:advances")
    assert test_db.query(ApiKey).one().scope_list() == ["v2:models", "v2:payouts", "v2:adhoc-payments"]


def test_custom_preset_needs_a_resource(client, test_db):
    _login_admin(client)
    resp = _create(client, name="Nothing", preset="custom")
    assert "Pick at least one resource" in resp.text
    assert test_db.query(ApiKey).count() == 0


def test_expiry_must_be_in_the_future(client, test_db):
    _login_admin(client)
    resp = _create(client, name="Past", preset="full", expires_at="2020-01-01T00:00+00:00")
    assert "Expiry must be in the future" in resp.text
    assert test_db.query(ApiKey).count() == 0


def test_expired_and_legacy_keys_are_labelled(client, test_db):
    from datetime import timedelta

    from app.api.keys import create_api_key_record
    from app.time_utils import utc_now

    create_api_key_record(test_db, name="Lapsed", created_by="admin", scopes=["v2:*"])
    ancient, _ = create_api_key_record(test_db, name="Ancient", created_by="admin", scopes=["v2:*"])
    ancient.scopes = '["v1:*"]'  # as stored before v1 was removed
    lapsed = test_db.query(ApiKey).filter_by(name="Lapsed").one()
    lapsed.expires_at = utc_now() - timedelta(days=1)
    test_db.commit()

    _login_admin(client)
    page = client.get("/admin/api-keys").text
    active, _, inactive = page.partition("Revoked and expired keys (1)")
    # Before: an expired key was listed as Active.
    assert "Lapsed" in inactive and "Lapsed" not in active
    assert "Expired" in inactive
    assert "this key no longer works" in active


def test_rotate_issues_a_replacement_and_keeps_the_old_key(client, test_db):
    _login_admin(client)
    _create(client, name="Partner", preset="salary")
    old = test_db.query(ApiKey).one()

    client.get("/admin/api-keys")
    resp = client.post(f"/admin/api-keys/{old.id}/rotate", data={"_csrf_token": csrf_token_for(client)})
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"
    plaintext = re.search(r'<pre id="new-api-key"[^>]*>(pd_[^<]+)</pre>', resp.text).group(1).strip()

    test_db.expire_all()
    keys = test_db.query(ApiKey).order_by(ApiKey.id).all()
    assert len(keys) == 2
    assert keys[0].revoked_at is None
    assert keys[1].name == "Partner"
    assert keys[1].scope_list() == keys[0].scope_list()
    assert keys[1].key_hash == hash_api_key(plaintext)
    assert test_db.query(AuditLog).filter(AuditLog.action == "rotate_api_key").count() == 1


def test_revoked_keys_cannot_be_rotated(client, test_db):
    _login_admin(client)
    _create(client, name="Gone", preset="full")
    key = test_db.query(ApiKey).one()
    client.get("/admin/api-keys")
    client.post(f"/admin/api-keys/{key.id}/revoke", data={"_csrf_token": csrf_token_for(client)})
    client.get("/admin/api-keys")
    resp = client.post(f"/admin/api-keys/{key.id}/rotate", data={"_csrf_token": csrf_token_for(client)})
    assert resp.status_code == 400


def test_v1_keys_cannot_be_rotated(client, test_db):
    from app.api.keys import create_api_key_record

    old, _ = create_api_key_record(test_db, name="Ancient", created_by="admin", scopes=["v2:*"])
    old.scopes = '["v1:*"]'  # as stored before v1 was removed
    test_db.commit()
    _login_admin(client)
    client.get("/admin/api-keys")
    resp = client.post(f"/admin/api-keys/{old.id}/rotate", data={"_csrf_token": csrf_token_for(client)})
    assert resp.status_code == 400
    assert test_db.query(ApiKey).count() == 1
