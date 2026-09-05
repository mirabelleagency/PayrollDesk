"""Tests for the external read-only API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.keys import create_api_key_record, revoke_api_key
from app.main import app
from app.models import (
    AdhocPayment,
    AdvanceRepayment,
    Model,
    ModelAdvance,
    ModelCompensationAdjustment,
    Payout,
    PayoutAdvanceAllocation,
    ScheduleRun,
    ValidationIssue,
)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def api_key_headers(test_db):
    _, plaintext = create_api_key_record(
        test_db, name="test-integration", created_by="admin", scopes=["v1:*"]
    )
    test_db.commit()
    return {"X-API-Key": plaintext}


def _seed_domain(test_db):
    model = Model(
        status="Active",
        code="API-001",
        real_name="Real Name",
        working_name="Working Name",
        start_date=date(2025, 1, 1),
        payment_method="ACH",
        payment_frequency="monthly",
        amount_monthly=Decimal("5000.00"),
        crypto_wallet="0xWALLET",
    )
    test_db.add(model)
    test_db.flush()

    run = ScheduleRun(
        target_year=2025,
        target_month=1,
        currency="USD",
        include_inactive=False,
        summary_models_paid=1,
        summary_total_payout=Decimal("1250.00"),
        summary_frequency_counts='{"monthly": 1}',
        export_path="exports",
    )
    test_db.add(run)
    test_db.flush()

    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id,
        pay_date=date(2025, 1, 15),
        code=model.code,
        real_name=model.real_name,
        working_name=model.working_name,
        payment_method=model.payment_method,
        payment_frequency=model.payment_frequency,
        amount=Decimal("1250.00"),
        status="paid",
        notes="January payout",
    )
    test_db.add(payout)
    test_db.flush()

    test_db.add(
        ValidationIssue(
            schedule_run_id=run.id,
            model_id=model.id,
            severity="warning",
            issue="Sample validation",
        )
    )
    test_db.add(
        AdhocPayment(
            model_id=model.id,
            pay_date=date(2025, 1, 20),
            amount=Decimal("100.00"),
            description="Bonus",
            status="paid",
        )
    )
    test_db.add(
        ModelCompensationAdjustment(
            model_id=model.id,
            effective_date=date(2025, 1, 1),
            amount_monthly=Decimal("5000.00"),
            notes="Initial",
        )
    )
    advance = ModelAdvance(
        model_id=model.id,
        amount_total=Decimal("1000.00"),
        amount_remaining=Decimal("500.00"),
        status="active",
        strategy="fixed",
        fixed_amount=Decimal("100.00"),
    )
    test_db.add(advance)
    test_db.flush()
    test_db.add(
        AdvanceRepayment(
            advance_id=advance.id,
            payout_id=payout.id,
            amount=Decimal("500.00"),
            source="auto",
        )
    )
    test_db.add(
        PayoutAdvanceAllocation(
            schedule_run_id=run.id,
            payout_id=payout.id,
            model_id=model.id,
            advance_id=advance.id,
            planned_amount=Decimal("100.00"),
        )
    )
    test_db.commit()
    return model, run, advance


def test_api_requires_key(client):
    resp = client.get("/api/v1/models")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"
    assert resp.headers.get("www-authenticate") == "APIKey"
    assert "location" not in resp.headers


def test_api_rejects_bad_key(client):
    resp = client.get("/api/v1/models", headers={"X-API-Key": "pd_invalid"})
    assert resp.status_code == 401


def test_api_rejects_revoked_key(client, test_db):
    record, plaintext = create_api_key_record(
        test_db, name="revoke-me", created_by="admin", scopes=["v1:*"]
    )
    test_db.commit()
    revoke_api_key(test_db, record.id)
    test_db.commit()
    resp = client.get("/api/v1/models", headers={"X-API-Key": plaintext})
    assert resp.status_code == 401


def test_api_models_list_and_detail(client, test_db, api_key_headers):
    model, _, _ = _seed_domain(test_db)
    resp = client.get("/api/v1/models", headers=api_key_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["has_more"] is False
    assert body["data"][0]["code"] == "API-001"
    assert body["data"][0]["amount_monthly"] == "5000.00"
    assert body["data"][0]["start_date"] == "2025-01-01"

    detail = client.get(f"/api/v1/models/{model.id}", headers=api_key_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["crypto_wallet"] == "0xWALLET"


def test_api_exact_code_filter(client, test_db, api_key_headers):
    _seed_domain(test_db)
    resp = client.get("/api/v1/models?code=API-001", headers=api_key_headers)
    assert len(resp.json()["data"]) == 1
    resp_partial = client.get("/api/v1/models?code=API", headers=api_key_headers)
    assert resp_partial.json()["data"] == []


def test_api_payouts_and_schedule_runs(client, test_db, api_key_headers):
    model, run, _ = _seed_domain(test_db)
    payouts = client.get("/api/v1/payouts", headers=api_key_headers).json()
    assert payouts["data"][0]["amount"] == "1250.00"
    assert payouts["data"][0]["crypto_wallet"] == "0xWALLET"
    assert payouts["data"][0]["model_id"] == model.id

    runs = client.get("/api/v1/schedule-runs", headers=api_key_headers).json()
    assert runs["data"][0]["summary_total_payout"] == "1250.00"
    assert runs["data"][0]["summary_frequency_counts"] == {"monthly": 1}

    detail = client.get(f"/api/v1/schedule-runs/{run.id}", headers=api_key_headers)
    assert detail.status_code == 200


def test_api_validation_adhoc_adjustments(client, test_db, api_key_headers):
    _seed_domain(test_db)
    assert client.get("/api/v1/validation-issues", headers=api_key_headers).json()["data"]
    assert client.get("/api/v1/adhoc-payments", headers=api_key_headers).json()["data"][0]["amount"] == "100.00"
    assert client.get("/api/v1/adjustments", headers=api_key_headers).json()["data"][0]["amount_monthly"] == "5000.00"


def test_api_advances_repayments_allocations(client, test_db, api_key_headers):
    _, _, advance = _seed_domain(test_db)
    advances = client.get("/api/v1/advances", headers=api_key_headers).json()
    assert advances["data"][0]["amount_remaining"] == "500.00"

    detail = client.get(f"/api/v1/advances/{advance.id}", headers=api_key_headers).json()
    assert len(detail["data"]["repayments"]) == 1

    repayments = client.get("/api/v1/advance-repayments", headers=api_key_headers).json()
    assert repayments["data"][0]["amount"] == "500.00"

    allocations = client.get("/api/v1/advance-allocations", headers=api_key_headers).json()
    assert allocations["data"][0]["planned_amount"] == "100.00"


def test_api_keyset_pagination(client, test_db, api_key_headers):
    for idx in range(3):
        test_db.add(
            Model(
                status="Active",
                code=f"PAG-{idx}",
                real_name=f"Real {idx}",
                working_name=f"Work {idx}",
                start_date=date(2025, 1, 1),
                payment_method="ACH",
                payment_frequency="monthly",
                amount_monthly=Decimal("100.00"),
            )
        )
    test_db.commit()

    first = client.get("/api/v1/models?limit=2", headers=api_key_headers).json()
    assert first["pagination"]["has_more"] is True
    assert first["pagination"]["next_cursor"] is not None

    second = client.get(
        f"/api/v1/models?limit=2&after_id={first['pagination']['next_cursor']}",
        headers=api_key_headers,
    ).json()
    assert len(second["data"]) >= 1


def test_api_invalid_date_range(client, api_key_headers):
    resp = client.get(
        "/api/v1/payouts?date_from=2025-02-01&date_to=2025-01-01",
        headers=api_key_headers,
    )
    assert resp.status_code == 400


def test_api_invalid_limit_returns_422(client, api_key_headers):
    resp = client.get("/api/v1/models?limit=501", headers=api_key_headers)
    assert resp.status_code == 422


def test_api_keyset_stable_when_middle_row_deleted(client, test_db, api_key_headers):
    ids = []
    for idx in range(4):
        model = Model(
            status="Active",
            code=f"DEL-{idx}",
            real_name=f"Real {idx}",
            working_name=f"Work {idx}",
            start_date=date(2025, 1, 1),
            payment_method="ACH",
            payment_frequency="monthly",
            amount_monthly=Decimal("100.00"),
        )
        test_db.add(model)
        test_db.flush()
        ids.append(model.id)
    test_db.commit()

    first = client.get("/api/v1/models?limit=2", headers=api_key_headers).json()
    assert first["pagination"]["has_more"] is True
    cursor = first["pagination"]["next_cursor"]

    middle = test_db.get(Model, ids[1])
    test_db.delete(middle)
    test_db.commit()

    second = client.get(
        f"/api/v1/models?limit=2&after_id={cursor}",
        headers=api_key_headers,
    ).json()
    returned_ids = {row["id"] for row in second["data"]}
    assert ids[0] not in returned_ids or ids[0] in {row["id"] for row in first["data"]}
    assert ids[1] not in returned_ids


def test_api_security_headers(client, api_key_headers):
    resp = client.get("/api/v1", headers=api_key_headers)
    assert resp.headers.get("cache-control") == "no-store"
    assert resp.headers.get("x-content-type-options") == "nosniff"
