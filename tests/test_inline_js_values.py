"""User-entered values are embedded in page scripts as JSON, not HTML-escaped text."""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Model


def test_purge_confirm_compares_against_the_real_code():
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code="O'NEIL&1", real_name="R", working_name="W",
            start_date=date(2025, 1, 1), payment_method="Wire", payment_frequency="monthly",
            amount_monthly=Decimal("100"),
        )
        session.add(model)
        session.commit()
        model_id = model.id
    finally:
        session.close()

    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    page = client.get(f"/admin/models/{model_id}/purge")
    assert page.status_code == 200
    # Before: '{{ impact.model_code }}' rendered as 'O&#39;NEIL&amp;1' inside the
    # script, so the typed code could never match and purge stayed disabled.
    assert "O&#39;NEIL" not in page.text.split("<script")[-1]
    assert r'!== "O\u0027NEIL\u00261"' in page.text
