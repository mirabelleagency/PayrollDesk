"""A prorated raise on a payout with an advance takes the advance off once."""
from datetime import date
from decimal import Decimal

from app import crud
from app.database import SessionLocal
from app.models import Model, ModelAdvance, Payout, PayoutAdvanceAllocation, ScheduleRun


def test_prorated_raise_with_advance_deducts_it_once():
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code="PRO1", real_name="R", working_name="W", start_date=date(2025, 1, 1),
            payment_method="Crypto", payment_frequency="monthly", amount_monthly=Decimal("2000"),
        )
        run = ScheduleRun(target_year=2026, target_month=10)
        session.add_all([model, run])
        session.flush()
        payout = Payout(
            schedule_run_id=run.id, model_id=model.id, pay_date=date(2026, 10, 31), code="PRO1",
            real_name="R", working_name="W", payment_method="Crypto", payment_frequency="monthly",
            amount=Decimal("1800"), gross_amount=Decimal("2000"), status="not_paid",
        )
        advance = ModelAdvance(
            model_id=model.id, amount_total=Decimal("1000"), amount_remaining=Decimal("1000"),
            status="active", strategy="fixed", fixed_amount=Decimal("200"),
        )
        session.add_all([payout, advance])
        session.flush()
        session.add(PayoutAdvanceAllocation(
            schedule_run_id=run.id, payout_id=payout.id, model_id=model.id,
            advance_id=advance.id, planned_amount=Decimal("200"),
        ))
        session.commit()

        [alert] = crud.generate_alerts_for_compensation_change(
            session, model=model, new_amount=Decimal("3000"), effective_date=date(2026, 10, 25)
        )
        session.commit()
        # 24/31 x 2000 + 7/31 x 3000, from gross — not from the 1800 net.
        assert alert.original_amount == Decimal("2000")
        assert alert.prorated_amount == Decimal("2225.81")

        crud.apply_alert_to_payout(session, alert, alert.prorated_amount, resolved_by="admin")
        session.commit()
        session.refresh(payout)
        assert payout.gross_amount == Decimal("2225.81")
        # Before: 1870.97 (advance taken off twice).
        assert payout.amount == Decimal("2025.81")
    finally:
        session.close()
