from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app import crud
from app.database import SessionLocal
from app.main import app
from app.models import AdhocPayment, Model, ScheduleRun


def _seed(session) -> int:
    run = ScheduleRun(
        target_year=2031,
        target_month=5,
        currency="USD",
        include_inactive=False,
        summary_models_paid=0,
        summary_total_payout=Decimal("0"),
        summary_frequency_counts="{}",
        export_path="exports",
    )
    model = Model(
        status="Active",
        code="RUNADHOC1",
        real_name="Real RUNADHOC1",
        working_name="Model RUNADHOC1",
        start_date=date(2031, 1, 1),
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount_monthly=Decimal("100.00"),
    )
    session.add_all([run, model])
    session.commit()
    session.add_all(
        [
            # Shown: pending in the run's month, and pending carried over from earlier.
            AdhocPayment(model_id=model.id, pay_date=date(2031, 5, 10), amount=Decimal("111.00"), description="in-month", status="pending"),
            AdhocPayment(model_id=model.id, pay_date=date(2031, 3, 2), amount=Decimal("22.00"), description="carried", status="pending"),
            # Hidden: paid, cancelled, or dated after the run's month.
            AdhocPayment(model_id=model.id, pay_date=date(2031, 5, 11), amount=Decimal("5.00"), description="paid-one", status="paid"),
            AdhocPayment(model_id=model.id, pay_date=date(2031, 5, 12), amount=Decimal("6.00"), description="cancelled-one", status="cancelled"),
            AdhocPayment(model_id=model.id, pay_date=date(2031, 6, 1), amount=Decimal("7.00"), description="next-month", status="pending"),
        ]
    )
    session.commit()
    return run.id


def test_unpaid_adhoc_through_month_filters_status_and_date():
    session = SessionLocal()
    try:
        _seed(session)
        payments = crud.list_unpaid_adhoc_payments_through_month(session, 2031, 5)
        descriptions = [p.description for p in payments if p.model and p.model.code == "RUNADHOC1"]
        assert descriptions == ["carried", "in-month"]
    finally:
        session.close()


def test_run_detail_shows_unpaid_adhoc_and_combined_total():
    session = SessionLocal()
    try:
        run_id = _seed(session)
    finally:
        session.close()

    client = TestClient(app)
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)

    resp = client.get(f"/schedules/{run_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "Unpaid Ad Hoc Payments" in html
    assert "in-month" in html and "carried" in html
    assert "Carried Over" in html
    for hidden in ("paid-one", "cancelled-one", "next-month"):
        assert hidden not in html
    assert 'id="combined-total">133.00' in html


def _admin_client() -> TestClient:
    client = TestClient(app)
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)
    return client


def test_run_csv_download_appends_unpaid_adhoc_rows():
    session = SessionLocal()
    try:
        run_id = _seed(session)
    finally:
        session.close()

    client = _admin_client()
    body = client.get(f"/schedules/{run_id}/download/schedule_csv").text
    assert "carried" in body and "in-month" in body and "Pending (Ad Hoc)" in body
    for hidden in ("paid-one", "cancelled-one", "next-month"):
        assert hidden not in body

    # A "paid" download only lists paid payouts, never pending ad hoc.
    paid_body = client.get(f"/schedules/{run_id}/download/schedule_csv?status=paid").text
    assert "Pending (Ad Hoc)" not in paid_body


def test_run_excel_download_includes_unpaid_adhoc_and_etag_tracks_them():
    import io

    import pandas as pd

    session = SessionLocal()
    try:
        run_id = _seed(session)
    finally:
        session.close()

    client = _admin_client()
    resp = client.get(f"/schedules/{run_id}/download/schedule_excel")
    assert resp.status_code == 200
    sheet = pd.read_excel(io.BytesIO(resp.content), sheet_name="Payouts")
    adhoc = sheet[sheet["Frequency"] == "Ad Hoc"]
    assert sorted(adhoc["Amount"].tolist()) == [22.0, 111.0]

    etag = resp.headers["ETag"]
    session = SessionLocal()
    try:
        payment = session.query(AdhocPayment).filter_by(description="carried").order_by(AdhocPayment.id.desc()).first()
        crud.set_adhoc_payment_status(session, payment, "paid")
    finally:
        session.close()

    resp = client.get(f"/schedules/{run_id}/download/schedule_excel", headers={"If-None-Match": etag})
    assert resp.status_code == 200
    assert resp.headers["ETag"] != etag
