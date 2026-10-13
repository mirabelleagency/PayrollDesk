"""Monthly amounts split exactly; pay-day settings can't break generation;
API key expiry is stored in UTC."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.payroll import ModelRecord, build_pay_schedule
from app.routers.admin_api_keys import _parse_expiry


def _record(frequency: str, monthly: str) -> ModelRecord:
    return ModelRecord(
        row_number=1, status="Active", code="SPLIT1", real_name="R", working_name="W",
        start_date=date(2025, 1, 1), payment_method="Crypto", payment_frequency=frequency,
        amount_monthly=Decimal(monthly),
    )


@pytest.mark.parametrize("frequency, monthly", [("weekly", "1000.01"), ("weekly", "333.33"), ("biweekly", "1000.01"), ("monthly", "999.99")])
def test_payouts_add_up_to_the_monthly_amount(frequency, monthly):
    df, _ = build_pay_schedule([_record(frequency, monthly)], 2026, 10, "USD")
    total = sum(Decimal(str(v)) for v in df["Amount (USD)"])
    # Before: 1000.01 weekly -> 4 x 250.00 = 1000.00 (a cent lost).
    assert total == Decimal(monthly)


def test_plan_pointing_past_pay_days_does_not_crash():
    df, _ = build_pay_schedule(
        [_record("weekly", "1000")], 2026, 10, "USD",
        pay_days=[7, 14, 21], frequency_plans={"weekly": [0, 1, 2, 3]},
    )
    # Before: IndexError aborted the whole run.
    assert len(df) == 3


@pytest.mark.parametrize("value, expected", [
    ("2099-11-01T17:00+08:00", datetime(2099, 11, 1, 9, 0)),
    ("2099-11-01T17:00", datetime(2099, 11, 1, 17, 0)),
    ("", None),
])
def test_api_key_expiry_is_utc(value, expected):
    assert _parse_expiry(value) == expected


def test_pay_config_refuses_days_that_collide():
    from fastapi.testclient import TestClient
    from app.main import app
    from conftest import csrf_token_for

    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    for days in ('[7, 14, 14, "eom"]', '[7, 14, 30, "eom"]', '[7, 14]'):
        token = csrf_token_for(client)
        resp = client.post(
            "/admin/settings/pay-config",
            data={"pay_days": days, "currency": "USD", "_csrf_token": token},
            headers={"X-CSRF-Token": token},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error=" in resp.headers["location"], days
