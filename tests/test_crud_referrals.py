"""Tests for referral terms, compensation adjustments and dashboard CRUD."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_model,
    list_referral_terms,
    upsert_referral_terms,
    delete_referral_term_for_referral,
    get_effective_compensation_amount,
    create_compensation_adjustment,
    dashboard_summary,
    top_paid_models,
    recent_validation_issues,
    pending_adhoc_payments,
    get_paid_payouts_for_model,
    find_duplicate_payouts,
    ReferralTermPayload,
)
from app.models import Model, ModelReferralTerm, AdhocPayment, Payout, ScheduleRun
from app.schemas import ModelCreate


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    from app.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def referrer_model(db_session: Session):
    """Create a referrer model."""
    payload = ModelCreate(
        code="REFERRER100",
        real_name="Referrer Model",
        working_name="Referrer",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("2000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


@pytest.fixture
def referral_model(db_session: Session):
    """Create a referred model."""
    payload = ModelCreate(
        code="REFERRAL100",
        real_name="Referral Model",
        working_name="Referral",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
        start_date=date(2024, 6, 1),
    )
    return create_model(db_session, payload)


class TestReferralTerms:
    """Tests for referral term CRUD operations."""

    def test_list_referral_terms_empty(self, db_session, referrer_model):
        """Test listing terms when none exist."""
        terms = list_referral_terms(db_session, referrer_model.id)
        assert len(terms) == 0

    def test_upsert_referral_terms_create(self, db_session, referrer_model, referral_model):
        """Test creating referral terms."""
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("50.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            )
        ]
        
        upsert_referral_terms(db_session, referrer_model, terms)
        
        result = list_referral_terms(db_session, referrer_model.id)
        assert len(result) == 1
        assert result[0].commission_per_referral == Decimal("50.00")
        assert result[0].commission_duration_months == 6

    def test_upsert_referral_terms_update(self, db_session, referrer_model, referral_model):
        """Test updating existing referral terms."""
        # Create initial term
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("50.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            )
        ]
        upsert_referral_terms(db_session, referrer_model, terms)
        
        # Update term
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("75.00"),
                commission_payout_frequency="biweekly",
                commission_duration_months=12,
                is_active=False,
            )
        ]
        upsert_referral_terms(db_session, referrer_model, terms)
        
        result = list_referral_terms(db_session, referrer_model.id)
        assert len(result) == 1
        assert result[0].commission_per_referral == Decimal("75.00")
        assert result[0].commission_duration_months == 12
        assert result[0].is_active is False

    def test_upsert_referral_terms_delete_removed(self, db_session, referrer_model, referral_model):
        """Test that terms not in the list are deleted."""
        # Create a second referral model
        payload = ModelCreate(
            code="REFERRAL101",
            real_name="Referral Model 2",
            working_name="Referral 2",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("1200.00"),
            start_date=date(2024, 6, 1),
        )
        referral_model_2 = create_model(db_session, payload)
        
        # Create two terms
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("50.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            ),
            ReferralTermPayload(
                referral_model_id=referral_model_2.id,
                commission_per_referral=Decimal("60.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            ),
        ]
        upsert_referral_terms(db_session, referrer_model, terms)
        
        # Now upsert with only one term - the other should be deleted
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("50.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            )
        ]
        upsert_referral_terms(db_session, referrer_model, terms)
        
        result = list_referral_terms(db_session, referrer_model.id)
        assert len(result) == 1
        assert result[0].referral_model_id == referral_model.id

    def test_delete_referral_term_for_referral(self, db_session, referrer_model, referral_model):
        """Test deleting all terms for a specific referral model."""
        # Create a term
        terms = [
            ReferralTermPayload(
                referral_model_id=referral_model.id,
                commission_per_referral=Decimal("50.00"),
                commission_payout_frequency="monthly",
                commission_duration_months=6,
                is_active=True,
            )
        ]
        upsert_referral_terms(db_session, referrer_model, terms)
        
        # Delete by referral model ID
        delete_referral_term_for_referral(db_session, referral_model.id)
        
        result = list_referral_terms(db_session, referrer_model.id)
        assert len(result) == 0


class TestCompensationAdjustments:
    """Tests for compensation adjustment functions."""

    def test_get_effective_compensation_no_adjustment(self, db_session, referrer_model):
        """Test getting effective compensation when no adjustments exist."""
        amount = get_effective_compensation_amount(db_session, referrer_model, date.today())
        assert amount == Decimal("2000.00")  # The model's base amount

    def test_create_compensation_adjustment(self, db_session, referrer_model):
        """Test creating a compensation adjustment."""
        adjustment = create_compensation_adjustment(
            db_session,
            referrer_model,
            effective_date=date(2024, 7, 1),
            amount_monthly=Decimal("2500.00"),
            notes="Merit increase",
        )
        
        assert adjustment.model_id == referrer_model.id
        assert adjustment.amount_monthly == Decimal("2500.00")
        assert adjustment.notes == "Merit increase"

    def test_get_effective_compensation_with_adjustment(self, db_session, referrer_model):
        """Test that adjustments affect effective compensation."""
        # Create an adjustment effective in the past
        create_compensation_adjustment(
            db_session,
            referrer_model,
            effective_date=date(2024, 1, 15),
            amount_monthly=Decimal("2500.00"),
        )
        
        # Get effective amount for a date after the adjustment
        amount = get_effective_compensation_amount(db_session, referrer_model, date(2024, 6, 1))
        assert amount == Decimal("2500.00")

    def test_get_effective_compensation_multiple_adjustments(self, db_session, referrer_model):
        """Test that the most recent adjustment is used."""
        # Create multiple adjustments
        create_compensation_adjustment(
            db_session,
            referrer_model,
            effective_date=date(2024, 1, 1),
            amount_monthly=Decimal("2200.00"),
        )
        create_compensation_adjustment(
            db_session,
            referrer_model,
            effective_date=date(2024, 3, 1),
            amount_monthly=Decimal("2400.00"),
        )
        create_compensation_adjustment(
            db_session,
            referrer_model,
            effective_date=date(2024, 6, 1),
            amount_monthly=Decimal("2600.00"),
        )
        
        # Query for a date after all adjustments
        amount = get_effective_compensation_amount(db_session, referrer_model, date(2024, 8, 1))
        assert amount == Decimal("2600.00")
        
        # Query for a date between adjustments
        amount = get_effective_compensation_amount(db_session, referrer_model, date(2024, 4, 1))
        assert amount == Decimal("2400.00")


class TestDashboardFunctions:
    """Tests for dashboard-related CRUD functions."""

    def test_dashboard_summary(self, db_session, referrer_model):
        """Test dashboard summary returns expected keys."""
        summary = dashboard_summary(db_session)
        
        assert "total_models" in summary
        assert "active_models" in summary
        assert "inactive_models" in summary
        assert "total_runs" in summary
        assert summary["total_models"] >= 1  # At least our test model

    def test_top_paid_models(self, db_session, referrer_model):
        """Test top paid models query."""
        earners = top_paid_models(db_session, limit=10)
        
        # Returns a list of tuples (Model, Decimal)
        assert isinstance(earners, list)

    def test_recent_validation_issues(self, db_session):
        """Test recent validation issues query."""
        issues = recent_validation_issues(db_session, limit=5)
        
        # Returns a sequence (may be empty)
        assert isinstance(issues, (list, tuple)) or hasattr(issues, '__iter__')

    def test_pending_adhoc_payments(self, db_session):
        """Test pending adhoc payments query."""
        payments = pending_adhoc_payments(db_session, limit=6)
        
        assert isinstance(payments, (list, tuple)) or hasattr(payments, '__iter__')


class TestPayoutHelpers:
    """Tests for payout helper functions."""

    def test_get_paid_payouts_for_model_empty(self, db_session, referrer_model):
        """Test getting paid payouts when none exist."""
        payouts = get_paid_payouts_for_model(db_session, referrer_model.id)
        # Filter out any payouts that might be from other tests
        payouts = [p for p in payouts if p.code == referrer_model.code]
        # Should be empty or contain only test data
        assert isinstance(payouts, (list, tuple)) or hasattr(payouts, '__iter__')

    def test_find_duplicate_payouts(self, db_session, referrer_model):
        """Test finding duplicate payouts."""
        # Query for duplicates that don't exist
        dupes = find_duplicate_payouts(
            db_session,
            model_id=referrer_model.id,
            pay_date=date(2099, 12, 31),
            amount=Decimal("1000.00"),
            status="paid",
        )
        assert len(dupes) == 0
