"""gross_amount stays equal to amount + advance deduction, and the v2 API keeps
paid history of deleted models."""
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app import crud
from app.api.keys import create_api_key_record
from app.database import SessionLocal
from app.main import app
from app.models import (
    Model,
    ModelAdvance,
    Payout,
    PayoutAdvanceAllocation,
    PayoutCompensationAlert,
    SyncState,
)
from tests.test_payout_notes import seed_run_with_payout


def _with_planned_advance(session, payout: Payout, planned: str) -> None:
    advance = ModelAdvance(
        model_id=payout.model_id,
        amount_total=Decimal("1000"),
        amount_remaining=Decimal("1000"),
        status="active",
    )
    session.add(advance)
    session.flush()
    session.add(
        PayoutAdvanceAllocation(
            schedule_run_id=payout.schedule_run_id,
            payout_id=payout.id,
            model_id=payout.model_id,
            advance_id=advance.id,
            planned_amount=Decimal(planned),
        )
    )
    # As generation does: net is gross minus the planned deduction.
    payout.gross_amount = Decimal("500")
    payout.amount = Decimal("500") - Decimal(planned)
    session.commit()


def test_applying_alert_keeps_the_advance_deduction():
    session = SessionLocal()
    try:
        _, payout = seed_run_with_payout(session)
        _with_planned_advance(session, payout, "100")
        alert = PayoutCompensationAlert(
            payout_id=payout.id,
            model_id=payout.model_id,
            schedule_run_id=payout.schedule_run_id,
            original_amount=Decimal("500"),
            new_amount=Decimal("600"),
            effective_date=date.today(),
        )
        session.add(alert)
        session.commit()

        crud.apply_alert_to_payout(session, alert, Decimal("600"), resolved_by="admin")
        session.commit()
        session.refresh(payout)

        # Before: amount became 600 (deduction lost) while gross stayed 500.
        assert payout.gross_amount == Decimal("600")
        assert payout.amount == Decimal("500")
    finally:
        session.close()


def test_lowering_paid_amount_lowers_gross():
    session = SessionLocal()
    try:
        _, payout = seed_run_with_payout(session)
        payout.gross_amount = Decimal("500")
        payout.amount = Decimal("500")
        session.commit()

        crud.set_payout_net(session, payout, Decimal("450"))
        session.commit()
        session.refresh(payout)

        # Before: gross stayed 500, so the API reported a 50 "advance deduction"
        # and a consumer adding it back counted 500.
        assert payout.amount == Decimal("450")
        assert payout.gross_amount == Decimal("450")
    finally:
        session.close()


def test_v2_lists_paid_payouts_of_deleted_models():
    session = SessionLocal()
    try:
        _, payout = seed_run_with_payout(session)
        payout.status = "paid"
        payout.gross_amount = payout.amount
        model = session.get(Model, payout.model_id)
        model.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        payout_id = payout.id

        _, key = create_api_key_record(session, name="m10", created_by="admin", scopes=["v2:*"])
        session.commit()
        revision = session.get(SyncState, 1).revision
    finally:
        session.close()

    with TestClient(app) as client:
        resp = client.get(
            f"/api/v2/payouts?snapshot_revision={revision}",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    rows = {row["id"]: row for row in resp.json()["data"]}
    assert payout_id in rows, "paid payout of a deleted model must stay in v2"
    assert rows[payout_id]["status"] == "paid"
    assert rows[payout_id]["current_model_crypto_wallet"] is None
