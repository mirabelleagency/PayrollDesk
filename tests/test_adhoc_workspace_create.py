"""Ad hoc payments can be recorded from the /schedules/adhoc workspace, not only a model's page."""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AdhocPayment, Model
from conftest import csrf_token_for


def _seed_model(code: str = "115 LEX", working_name: str = "Lexi") -> int:
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code=code, real_name="R", working_name=working_name, start_date=date(2025, 1, 1),
            payment_method="Crypto", payment_frequency="monthly", amount_monthly=Decimal("100"),
        )
        session.add(model)
        session.commit()
        return model.id
    finally:
        session.close()


def _admin() -> TestClient:
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    return client


def _post(client, data):
    token = csrf_token_for(client)
    return client.post(
        "/schedules/adhoc", data={**data, "_csrf_token": token}, headers={"X-CSRF-Token": token}, follow_redirects=False
    )


def _payments(model_id: int) -> list[AdhocPayment]:
    session = SessionLocal()
    try:
        return session.query(AdhocPayment).filter_by(model_id=model_id).all()
    finally:
        session.close()


def test_creates_payment_from_picker_label():
    model_id = _seed_model()
    response = _post(_admin(), {
        "model": "115 LEX · Lexi", "pay_date": "2026-10-13", "amount": "72.10", "description": "Hotel",
    })
    assert response.status_code == 303
    assert response.headers["location"].startswith("/schedules/adhoc?success=")
    [payment] = _payments(model_id)
    assert payment.amount == Decimal("72.10")
    assert payment.pay_date == date(2026, 10, 13)
    assert payment.description == "Hotel"
    assert payment.status == "pending"


def test_accepts_a_bare_code_case_insensitively():
    model_id = _seed_model()
    _post(_admin(), {"model": "115 lex", "pay_date": "2026-10-13", "amount": "10"})
    assert len(_payments(model_id)) == 1


def test_accepts_the_code_number_when_unambiguous():
    model_id = _seed_model()
    _post(_admin(), {"model": "115", "pay_date": "2026-10-13", "amount": "10"})
    assert len(_payments(model_id)) == 1


def test_ambiguous_code_number_writes_nothing():
    first = _seed_model("120 ANA", "Ana")
    second = _seed_model("120 BEA", "Bea")
    response = _post(_admin(), {"model": "120", "pay_date": "2026-10-13", "amount": "10"})
    assert "error=" in response.headers["location"]
    assert _payments(first) == [] and _payments(second) == []


def test_unknown_model_writes_nothing():
    model_id = _seed_model()
    response = _post(_admin(), {"model": "999 NOPE", "pay_date": "2026-10-13", "amount": "10"})
    assert "error=" in response.headers["location"]
    assert _payments(model_id) == []


def test_invalid_amount_writes_nothing():
    model_id = _seed_model()
    for amount in ("0", "-5", "abc", "NaN"):
        response = _post(_admin(), {"model": "115 LEX", "pay_date": "2026-10-13", "amount": amount})
        assert "error=" in response.headers["location"]
    assert _payments(model_id) == []


def test_workspace_page_shows_the_form_and_sidebar_link():
    _seed_model()
    page = _admin().get("/schedules/adhoc")
    assert page.status_code == 200
    assert 'action="/schedules/adhoc"' in page.text
    assert "115 LEX · Lexi" in page.text
    assert 'href="/schedules/adhoc"' in page.text
