"""Tests for CommissionPayout CRUD operations."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    CommissionPayoutCreate,
    bulk_update_commission_payout_status,
    count_commission_payouts,
    create_commission_payout,
    create_model,
    delete_commission_payout,
    delete_commission_payouts_by_model,
    get_commission_payout,
    get_or_create_commission_payout,
    list_commission_payouts,
    sum_commission_payouts,
    update_commission_payout_status,
)
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
    """Create a referrer model for tests."""
    payload = ModelCreate(
        code="REF001",
        real_name="Referrer Real Name",
        working_name="Referrer Model",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


@pytest.fixture
def referral_model(db_session: Session):
    """Create a referral model for tests."""
    payload = ModelCreate(
        code="NEW001",
        real_name="Referral Real Name",
        working_name="Referred Model",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("800.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


class TestCreateCommissionPayout:
    """Tests for create_commission_payout."""

    def test_create_commission_payout(self, db_session, referrer_model, referral_model):
        """Test creating a commission payout."""
        payload = CommissionPayoutCreate(
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 1, 15),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        payout = create_commission_payout(db_session, payload)
        
        assert payout.id is not None
        assert payout.referrer_model_id == referrer_model.id
        assert payout.referral_model_id == referral_model.id
        assert payout.pay_date == date(2025, 1, 15)
        assert payout.schedule_type == "monthly"
        assert payout.amount == Decimal("100.00")
        assert payout.status == "unpaid"

    def test_create_commission_payout_with_status(self, db_session, referrer_model, referral_model):
        """Test creating a commission payout with explicit status."""
        payload = CommissionPayoutCreate(
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 1, 15),
            schedule_type="mid-month",
            amount=Decimal("50.00"),
            status="paid",
        )
        payout = create_commission_payout(db_session, payload)
        
        assert payout.status == "paid"
        assert payout.schedule_type == "mid-month"


class TestGetOrCreateCommissionPayout:
    """Tests for get_or_create_commission_payout."""

    def test_creates_new_payout(self, db_session, referrer_model, referral_model):
        """Test that it creates a new payout when none exists."""
        payout, created = get_or_create_commission_payout(
            db_session,
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 2, 1),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        
        assert created is True
        assert payout.id is not None
        assert payout.status == "unpaid"

    def test_returns_existing_payout(self, db_session, referrer_model, referral_model):
        """Test that it returns existing payout without creating duplicate."""
        # Create first
        payout1, created1 = get_or_create_commission_payout(
            db_session,
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 2, 1),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        
        # Try to create again
        payout2, created2 = get_or_create_commission_payout(
            db_session,
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 2, 1),
            schedule_type="monthly",
            amount=Decimal("200.00"),  # Different amount
        )
        
        assert created1 is True
        assert created2 is False
        assert payout1.id == payout2.id
        assert payout2.amount == Decimal("100.00")  # Original amount preserved


class TestListCommissionPayouts:
    """Tests for list_commission_payouts."""

    def test_list_all_payouts(self, db_session, referrer_model, referral_model):
        """Test listing all commission payouts."""
        # Create multiple payouts
        for i in range(3):
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 1 + i, 15),
                schedule_type="monthly",
                amount=Decimal(f"{100 + i * 10}.00"),
            )
            create_commission_payout(db_session, payload)
        
        payouts = list_commission_payouts(db_session)
        assert len(payouts) >= 3

    def test_list_payouts_with_status_filter(self, db_session, referrer_model, referral_model):
        """Test filtering payouts by status."""
        # Create paid and unpaid payouts
        for status in ["paid", "unpaid"]:
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 1, 15) if status == "paid" else date(2025, 2, 15),
                schedule_type="monthly",
                amount=Decimal("100.00"),
                status=status,
            )
            create_commission_payout(db_session, payload)
        
        paid_payouts = list_commission_payouts(db_session, status="paid")
        unpaid_payouts = list_commission_payouts(db_session, status="unpaid")
        
        assert all(p.status == "paid" for p in paid_payouts)
        assert all(p.status == "unpaid" for p in unpaid_payouts)

    def test_list_payouts_with_date_range(self, db_session, referrer_model, referral_model):
        """Test filtering payouts by date range."""
        # Create payouts across different dates
        dates = [date(2025, 1, 15), date(2025, 3, 15), date(2025, 6, 15)]
        for d in dates:
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=d,
                schedule_type="monthly",
                amount=Decimal("100.00"),
            )
            create_commission_payout(db_session, payload)
        
        # Filter to Q1 2025
        q1_payouts = list_commission_payouts(
            db_session,
            pay_date_from=date(2025, 1, 1),
            pay_date_to=date(2025, 3, 31),
        )
        
        # Should include January and March, not June
        assert all(p.pay_date <= date(2025, 3, 31) for p in q1_payouts)


class TestCountAndSumCommissionPayouts:
    """Tests for count_commission_payouts and sum_commission_payouts."""

    def test_count_payouts(self, db_session, referrer_model, referral_model):
        """Test counting commission payouts."""
        initial_count = count_commission_payouts(db_session)
        
        # Create 2 payouts
        for i in range(2):
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 4 + i, 15),
                schedule_type="monthly",
                amount=Decimal("100.00"),
            )
            create_commission_payout(db_session, payload)
        
        assert count_commission_payouts(db_session) == initial_count + 2

    def test_sum_payouts(self, db_session, referrer_model, referral_model):
        """Test summing commission payout amounts."""
        # Create payouts with specific amounts
        amounts = [Decimal("100.00"), Decimal("150.00"), Decimal("75.50")]
        for i, amount in enumerate(amounts):
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 7 + i, 15),
                schedule_type="monthly",
                amount=amount,
            )
            create_commission_payout(db_session, payload)
        
        total = sum_commission_payouts(
            db_session,
            referrer_model_id=referrer_model.id,
        )
        
        assert total >= sum(amounts)


class TestUpdateCommissionPayoutStatus:
    """Tests for update_commission_payout_status."""

    def test_update_status_to_paid(self, db_session, referrer_model, referral_model):
        """Test updating status from unpaid to paid."""
        payload = CommissionPayoutCreate(
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 10, 15),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        payout = create_commission_payout(db_session, payload)
        
        updated = update_commission_payout_status(db_session, payout, "paid")
        
        assert updated.status == "paid"
        assert updated.updated_at is not None

    def test_invalid_status_raises_error(self, db_session, referrer_model, referral_model):
        """Test that invalid status raises ValueError."""
        payload = CommissionPayoutCreate(
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 10, 20),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        payout = create_commission_payout(db_session, payload)
        
        with pytest.raises(ValueError) as exc_info:
            update_commission_payout_status(db_session, payout, "invalid")
        
        assert "Invalid status" in str(exc_info.value)


class TestBulkUpdateCommissionPayoutStatus:
    """Tests for bulk_update_commission_payout_status."""

    def test_bulk_update_status(self, db_session, referrer_model, referral_model):
        """Test bulk updating status for multiple payouts."""
        # Create multiple unpaid payouts
        payout_ids = []
        for i in range(3):
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 11, 1 + i),
                schedule_type="monthly",
                amount=Decimal("100.00"),
            )
            payout = create_commission_payout(db_session, payload)
            payout_ids.append(payout.id)
        
        # Bulk update to paid
        updated_count = bulk_update_commission_payout_status(db_session, payout_ids, "paid")
        
        assert updated_count == 3
        
        # Verify all are paid
        for payout_id in payout_ids:
            payout = get_commission_payout(db_session, payout_id)
            assert payout.status == "paid"

    def test_bulk_update_empty_list(self, db_session):
        """Test bulk update with empty list returns 0."""
        result = bulk_update_commission_payout_status(db_session, [], "paid")
        assert result == 0


class TestDeleteCommissionPayout:
    """Tests for delete functions."""

    def test_delete_single_payout(self, db_session, referrer_model, referral_model):
        """Test deleting a single commission payout."""
        payload = CommissionPayoutCreate(
            referrer_model_id=referrer_model.id,
            referral_model_id=referral_model.id,
            pay_date=date(2025, 12, 15),
            schedule_type="monthly",
            amount=Decimal("100.00"),
        )
        payout = create_commission_payout(db_session, payload)
        payout_id = payout.id
        
        delete_commission_payout(db_session, payout)
        
        assert get_commission_payout(db_session, payout_id) is None

    def test_delete_payouts_by_model(self, db_session, referrer_model, referral_model):
        """Test deleting all payouts for a model."""
        # Create payouts where referrer_model is the referrer
        for i in range(2):
            payload = CommissionPayoutCreate(
                referrer_model_id=referrer_model.id,
                referral_model_id=referral_model.id,
                pay_date=date(2025, 12, 20 + i),
                schedule_type="monthly",
                amount=Decimal("100.00"),
            )
            create_commission_payout(db_session, payload)
        
        initial_count = count_commission_payouts(db_session, referrer_model_id=referrer_model.id)
        assert initial_count >= 2
        
        deleted_count = delete_commission_payouts_by_model(db_session, referrer_model.id)
        
        assert deleted_count >= 2
        assert count_commission_payouts(db_session, referrer_model_id=referrer_model.id) == 0
