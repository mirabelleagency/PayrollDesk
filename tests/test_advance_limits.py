"""Advance guardrails: minimum take-home, max per run, cap multiplier."""
from datetime import date
from decimal import Decimal

from app import crud
from app.database import SessionLocal
from app.models import Model, ModelAdvance, Payout, PayoutAdvanceAllocation, ScheduleRun


def _setup(session, payout_amounts, **advance_kwargs):
    model = Model(
        status="Active", code="LIM1", real_name="R", working_name="W", start_date=date(2025, 1, 1),
        payment_method="Crypto", payment_frequency="weekly", amount_monthly=Decimal("2000"),
    )
    session.add(model)
    session.flush()
    advance = ModelAdvance(
        model_id=model.id, amount_total=Decimal("1000"), amount_remaining=Decimal("1000"),
        status="active", strategy="fixed", fixed_amount=Decimal("100"), **advance_kwargs,
    )
    run = ScheduleRun(target_year=2026, target_month=10)
    session.add_all([advance, run])
    session.flush()
    payouts = []
    for day, amount in zip((7, 14, 21, 31), payout_amounts):
        p = Payout(
            schedule_run_id=run.id, model_id=model.id, pay_date=date(2026, 10, day), code="LIM1",
            real_name="R", working_name="W", payment_method="Crypto", payment_frequency="weekly",
            amount=Decimal(amount), gross_amount=Decimal(amount), status="not_paid",
        )
        session.add(p)
        payouts.append(p)
    session.flush()
    crud._apply_advance_allocations_for_run(session, run, payouts)
    session.commit()
    return [
        sum((a.planned_amount for a in session.query(PayoutAdvanceAllocation).filter_by(payout_id=p.id)), Decimal("0"))
        for p in payouts
    ]


def test_defaults_do_not_limit():
    session = SessionLocal()
    try:
        assert _setup(session, ["500"] * 4) == [Decimal("100")] * 4
    finally:
        session.close()


def test_min_take_home_is_kept():
    session = SessionLocal()
    try:
        # 500 payout, take-home must stay >= 450 -> only 50 can come off.
        assert _setup(session, ["500", "420", "500", "500"], min_net_floor=Decimal("450")) == [
            Decimal("50"), Decimal("0"), Decimal("50"), Decimal("50"),
        ]
    finally:
        session.close()


def test_max_per_run_caps_the_month():
    session = SessionLocal()
    try:
        assert _setup(session, ["500"] * 4, max_per_run=Decimal("150")) == [
            Decimal("100"), Decimal("50"), Decimal("0"), Decimal("0"),
        ]
    finally:
        session.close()


def test_cap_multiplier_scales_the_deduction():
    session = SessionLocal()
    try:
        assert _setup(session, ["500"] * 4, cap_multiplier=Decimal("0.5")) == [Decimal("50")] * 4
    finally:
        session.close()


def test_create_advance_defaults_are_non_blocking():
    session = SessionLocal()
    try:
        model = Model(
            status="Active", code="LIM2", real_name="R", working_name="W", start_date=date(2025, 1, 1),
            payment_method="Crypto", payment_frequency="weekly", amount_monthly=Decimal("2000"),
        )
        session.add(model)
        session.commit()
        adv = crud.create_advance(session, model, amount_total=Decimal("750"), strategy="fixed", fixed_amount=Decimal("100"))
        assert adv.min_net_floor == Decimal("0")
        assert adv.max_per_run == Decimal("750")
    finally:
        session.close()
