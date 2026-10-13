"""Editing an ad hoc payment's notes keeps its description; paid ones can't be deleted."""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AdhocPayment, Model
from conftest import csrf_token_for


def _seed(status: str) -> tuple[int, int]:
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code="ADH1", real_name="R", working_name="W", start_date=date(2025, 1, 1),
            payment_method="Crypto", payment_frequency="monthly", amount_monthly=Decimal("100"),
        )
        session.add(model)
        session.flush()
        payment = AdhocPayment(
            model_id=model.id, pay_date=date(2026, 7, 31), amount=Decimal("72.10"),
            description="Hotel Cham Cham - Taipei", status=status,
        )
        session.add(payment)
        session.commit()
        return model.id, payment.id
    finally:
        session.close()


def _admin() -> TestClient:
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    return client


def _post(client, path, data):
    token = csrf_token_for(client)
    return client.post(path, data={**data, "_csrf_token": token}, headers={"X-CSRF-Token": token}, follow_redirects=False)


def test_editing_notes_keeps_the_description():
    model_id, payment_id = _seed("paid")
    _post(_admin(), f"/models/{model_id}/adhoc-payments/{payment_id}/notes", {"notes": "receipt filed"})
    session = SessionLocal()
    try:
        payment = session.get(AdhocPayment, payment_id)
        assert payment.notes == "receipt filed"
        # Before: None.
        assert payment.description == "Hotel Cham Cham - Taipei"
    finally:
        session.close()


def test_paid_adhoc_payment_cannot_be_deleted():
    model_id, payment_id = _seed("paid")
    _post(_admin(), f"/models/{model_id}/adhoc-payments/{payment_id}/delete", {})
    session = SessionLocal()
    try:
        assert session.get(AdhocPayment, payment_id) is not None
    finally:
        session.close()


def test_pending_adhoc_payment_can_be_deleted():
    model_id, payment_id = _seed("pending")
    _post(_admin(), f"/models/{model_id}/adhoc-payments/{payment_id}/delete", {})
    session = SessionLocal()
    try:
        assert session.get(AdhocPayment, payment_id) is None
    finally:
        session.close()
