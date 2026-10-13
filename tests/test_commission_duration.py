"""Referral commissions stop after the agreed number of months."""
from datetime import date
from decimal import Decimal

from app.commission import generate_referral_schedule
from app.database import SessionLocal
from app.models import Model, ModelReferralTerm


def _model(code: str, start: date, **extra) -> Model:
    return Model(
        status="Active", code=code, real_name=f"Real {code}", working_name=f"Working {code}",
        start_date=start, payment_method="Crypto", payment_frequency="monthly",
        amount_monthly=Decimal("1000"), **extra,
    )


def _schedule(duration_months):
    session = SessionLocal()
    try:
        # Referral terms aren't part of the shared per-test cleanup.
        session.query(ModelReferralTerm).delete()
        session.commit()
        referrer = _model("REF1", date(2025, 1, 1))
        session.add(referrer)
        session.flush()
        referral = _model("REF2", date(2026, 1, 10), referred_by_model_id=referrer.id)
        session.add(referral)
        session.flush()
        session.add(ModelReferralTerm(
            referrer_model_id=referrer.id, referral_model_id=referral.id,
            commission_per_referral=Decimal("50"), commission_payout_frequency="dual",
            commission_duration_months=duration_months, is_active=True,
        ))
        session.commit()
        entries = generate_referral_schedule(session, months_forward=6, today=date(2026, 1, 1))
        return [e.pay_date for e in entries]
    finally:
        session.close()


def test_commission_ends_after_its_duration():
    # Started 2026-01-10 for 2 months: Jan 14, Feb 1, Feb 14 — nothing from March.
    # Before: it ran through the whole 6-month horizon.
    assert _schedule(2) == [date(2026, 1, 14), date(2026, 2, 1), date(2026, 2, 14)]


def test_no_duration_means_open_ended():
    assert len(_schedule(None)) == 11  # Jan 14, then 1st & 14th of Feb–Jun
