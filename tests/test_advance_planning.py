"""Advance deductions planned across several unpaid schedule runs."""
from datetime import date
from decimal import Decimal

from app import crud
from app.database import SessionLocal
from app.models import (
    AdvanceRepayment,
    Model,
    ModelAdvance,
    Payout,
    PayoutAdvanceAllocation,
    ScheduleRun,
)


def _setup(session, remaining: str):
    model = Model(
        status="Active",
        code="ADV1",
        real_name="Real ADV1",
        working_name="Model ADV1",
        start_date=date(2025, 1, 1),
        payment_method="Crypto",
        payment_frequency="monthly",
        amount_monthly=Decimal("500"),
    )
    session.add(model)
    session.flush()
    advance = ModelAdvance(
        model_id=model.id,
        amount_total=Decimal(remaining),
        amount_remaining=Decimal(remaining),
        status="active",
        strategy="fixed",
        fixed_amount=Decimal("100"),
    )
    session.add(advance)
    runs_and_payouts = []
    for month in (10, 11):
        run = ScheduleRun(target_year=2026, target_month=month)
        session.add(run)
        session.flush()
        payout = Payout(
            schedule_run_id=run.id,
            model_id=model.id,
            pay_date=date(2026, month, 28),
            code=model.code,
            real_name=model.real_name,
            working_name=model.working_name,
            payment_method="Crypto",
            payment_frequency="monthly",
            amount=Decimal("500"),
            gross_amount=Decimal("500"),
            status="not_paid",
        )
        session.add(payout)
        session.flush()
        runs_and_payouts.append((run, payout))
    session.commit()
    return advance, runs_and_payouts


def _planned(session, payout: Payout) -> Decimal:
    return sum(
        (a.planned_amount for a in session.query(PayoutAdvanceAllocation).filter_by(payout_id=payout.id)),
        Decimal("0"),
    )


def test_second_run_does_not_plan_balance_already_planned():
    session = SessionLocal()
    try:
        advance, [(oct_run, oct_payout), (nov_run, nov_payout)] = _setup(session, "100")

        crud._apply_advance_allocations_for_run(session, oct_run, [oct_payout])
        crud._apply_advance_allocations_for_run(session, nov_run, [nov_payout])
        session.commit()

        # October takes the whole 100; nothing is left for November to plan.
        assert _planned(session, oct_payout) == Decimal("100")
        assert _planned(session, nov_payout) == Decimal("0")
        assert nov_payout.amount == Decimal("500")

        # Paying both months now works; before, November's payment failed.
        assert crud.update_payout(session, oct_payout, None, "paid") == Decimal("100")
        assert crud.update_payout(session, nov_payout, None, "paid") == Decimal("0")
        session.refresh(advance)
        assert advance.amount_remaining == Decimal("0")
        assert session.query(AdvanceRepayment).count() == 1
    finally:
        session.close()


def test_partial_balance_is_split_across_runs():
    session = SessionLocal()
    try:
        _, [(oct_run, oct_payout), (nov_run, nov_payout)] = _setup(session, "150")

        crud._apply_advance_allocations_for_run(session, oct_run, [oct_payout])
        crud._apply_advance_allocations_for_run(session, nov_run, [nov_payout])
        session.commit()

        assert _planned(session, oct_payout) == Decimal("100")
        assert _planned(session, nov_payout) == Decimal("50")
        assert nov_payout.amount == Decimal("450")
    finally:
        session.close()
