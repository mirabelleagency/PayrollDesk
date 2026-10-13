"""An Excel import with a bad row imports nothing."""
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Model, Payout
from conftest import csrf_token_for


def _workbook(payout_rows) -> bytes:
    models = pd.DataFrame([
        {"Code": "IMP1", "Status": "Active", "Real Name": "Real One", "Working Name": "One",
         "Start Date": "2024-01-01", "Payment Method": "Wire", "Payment Frequency": "Monthly",
         "Monthly Amount": 1000, "Crypto Wallet": ""},
    ])
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        models.to_excel(writer, sheet_name="Models", index=False)
        pd.DataFrame(payout_rows, columns=["Code", "Pay Date", "Amount", "Status"]).to_excel(
            writer, sheet_name="Payouts", index=False
        )
    return buffer.getvalue()


def _import(workbook: bytes):
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    token = csrf_token_for(client)
    return client.post(
        "/models/import",
        data={"auto_runs": "on", "_csrf_token": token},
        files={"excel_file": ("payroll.xlsx", workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"X-CSRF-Token": token},
    )


def _counts():
    session = SessionLocal()
    try:
        return session.query(Model).filter(Model.code == "IMP1").count(), session.query(Payout).count()
    finally:
        session.close()


def test_one_bad_row_imports_nothing():
    resp = _import(_workbook([
        {"Code": "IMP1", "Pay Date": "2024-02-01", "Amount": 500, "Status": "Paid"},
        {"Code": "NOPE", "Pay Date": "2024-02-14", "Amount": 500, "Status": "Paid"},  # unknown model
    ]))
    assert resp.status_code == 200
    assert "Import not applied" in resp.text
    assert "NOPE" in resp.text
    # Before: the model and the good payout were committed anyway.
    assert _counts() == (0, 0)


def test_clean_file_imports_everything():
    resp = _import(_workbook([
        {"Code": "IMP1", "Pay Date": "2024-02-01", "Amount": 500, "Status": "Paid"},
    ]))
    assert resp.status_code == 200
    assert "Import complete" in resp.text
    assert _counts() == (1, 1)


def test_empty_payouts_sheet_is_not_an_error():
    resp = _import(_workbook([]))
    assert "Import complete" in resp.text
    assert "Payouts sheet is empty" in resp.text
    assert _counts() == (1, 0)
