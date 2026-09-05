"""Tests for the external read-only API v2."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.keys import create_api_key_record
from app.main import app
from app.models import Model, Payout, ScheduleRun, SyncState


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def v2_headers(test_db):
    _, plaintext = create_api_key_record(
        test_db,
        name="v2-integration",
        created_by="admin",
        scopes=["v2:*"],
    )
    test_db.commit()
    return {"X-API-Key": plaintext}


def test_v2_snapshot_requires_auth(client):
    resp = client.get("/api/v2/snapshot")
    assert resp.status_code == 401


def test_v2_snapshot_returns_revision(client, test_db, v2_headers):
    sync = test_db.get(SyncState, 1)
    assert sync is not None
    resp = client.get("/api/v2/snapshot", headers=v2_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_version"] == "2"
    assert body["revision"] == sync.revision
    assert "models" in body["collections"]


def test_v2_first_page_requires_snapshot_revision(client, v2_headers):
    resp = client.get("/api/v2/models", headers=v2_headers)
    assert resp.status_code == 400


def test_v2_models_collection(client, test_db, v2_headers):
    model = Model(
        status="Active",
        code="V2-001",
        real_name="Real",
        working_name="Working",
        start_date=date(2025, 1, 1),
        payment_method="ACH",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
    )
    test_db.add(model)
    test_db.commit()
    revision = test_db.get(SyncState, 1).revision

    resp = client.get(
        f"/api/v2/models?snapshot_revision={revision}",
        headers=v2_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_version"] == "2"
    assert body["snapshot_revision"] == revision
    assert body["data"][0]["created_at"].endswith("Z")
    assert body["data"][0]["code"] == "V2-001"


def test_v2_write_methods_rejected(client, v2_headers):
    for method in ("post", "put", "patch", "delete"):
        resp = client.request(method, "/api/v2/models", headers=v2_headers)
        assert resp.status_code == 405


def test_v2_scope_denial(client, test_db):
    _, plaintext = create_api_key_record(
        test_db,
        name="v2-models-only",
        created_by="admin",
        scopes=["v2:models"],
    )
    test_db.commit()
    revision = test_db.get(SyncState, 1).revision
    headers = {"X-API-Key": plaintext}
    assert client.get(f"/api/v2/models?snapshot_revision={revision}", headers=headers).status_code == 200
    assert client.get(f"/api/v2/payouts?snapshot_revision={revision}", headers=headers).status_code == 403
