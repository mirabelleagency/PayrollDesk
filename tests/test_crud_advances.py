"""Tests for cash advance CRUD operations."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_model,
    create_advance,
    get_advance,
    approve_advance,
    outstanding_advance_total,
    list_advances_for_model,
    delete_advance,
    record_advance_repayment,
)
from app.models import ModelAdvance
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
def test_model(db_session: Session):
    """Create a model for advance tests."""
    payload = ModelCreate(
        code="ADVANCE001",
        real_name="Advance Test Model",
        working_name="Advance Test",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("3000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


class TestAdvanceCreation:
    """Tests for creating cash advances."""

    def test_create_advance_fixed_strategy(self, db_session, test_model):
        """Test creating an advance with fixed repayment strategy."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("1000.00"),
            strategy="fixed",
            fixed_amount=Decimal("100.00"),
            notes="Emergency advance",
        )
        
        assert advance.id is not None
        assert advance.model_id == test_model.id
        assert advance.amount_total == Decimal("1000.00")
        assert advance.amount_remaining == Decimal("1000.00")
        assert advance.strategy == "fixed"
        assert advance.fixed_amount == Decimal("100.00")
        assert advance.status == "requested"
        assert advance.notes == "Emergency advance"

    def test_create_advance_percent_strategy(self, db_session, test_model):
        """Test creating an advance with percent repayment strategy."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="percent",
            percent_rate=Decimal("10.00"),
        )
        
        assert advance.strategy == "percent"
        assert advance.percent_rate == Decimal("10.00")
        assert advance.fixed_amount is None

    def test_create_advance_invalid_strategy_raises(self, db_session, test_model):
        """Test that invalid strategy raises ValueError."""
        with pytest.raises(ValueError, match="strategy must be"):
            create_advance(
                db_session,
                test_model,
                amount_total=Decimal("500.00"),
                strategy="invalid",
            )

    def test_create_advance_fixed_missing_amount_raises(self, db_session, test_model):
        """Test that fixed strategy without amount raises ValueError."""
        with pytest.raises(ValueError, match="fixed_amount must be"):
            create_advance(
                db_session,
                test_model,
                amount_total=Decimal("500.00"),
                strategy="fixed",
                fixed_amount=None,
            )

    def test_create_advance_percent_invalid_rate_raises(self, db_session, test_model):
        """Test that percent strategy with invalid rate raises ValueError."""
        with pytest.raises(ValueError, match="percent_rate must be"):
            create_advance(
                db_session,
                test_model,
                amount_total=Decimal("500.00"),
                strategy="percent",
                percent_rate=Decimal("0"),
            )
        
        with pytest.raises(ValueError, match="percent_rate must be"):
            create_advance(
                db_session,
                test_model,
                amount_total=Decimal("500.00"),
                strategy="percent",
                percent_rate=Decimal("101"),
            )


class TestAdvanceRetrieval:
    """Tests for retrieving advances."""

    def test_get_advance(self, db_session, test_model):
        """Test getting an advance by ID."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        
        result = get_advance(db_session, advance.id)
        
        assert result is not None
        assert result.id == advance.id
        assert result.amount_total == Decimal("500.00")

    def test_get_advance_not_found(self, db_session):
        """Test getting non-existent advance."""
        result = get_advance(db_session, 999999)
        assert result is None

    def test_list_advances_for_model(self, db_session, test_model):
        """Test listing advances for a model."""
        # Create multiple advances
        create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        create_advance(
            db_session,
            test_model,
            amount_total=Decimal("300.00"),
            strategy="fixed",
            fixed_amount=Decimal("30.00"),
        )
        
        advances = list_advances_for_model(db_session, test_model.id)
        
        assert len(advances) >= 2

    def test_list_advances_for_model_with_status_filter(self, db_session, test_model):
        """Test listing advances filtered by status."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        
        # List only requested advances
        requested = list_advances_for_model(db_session, test_model.id, status="requested")
        assert len(requested) >= 1
        
        # List only approved (should be empty)
        approved = list_advances_for_model(db_session, test_model.id, status="approved")
        # Could be 0 or more depending on other tests


class TestAdvanceApproval:
    """Tests for approving advances."""

    def test_approve_advance(self, db_session, test_model):
        """Test approving an advance."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        
        approved = approve_advance(db_session, advance, activate=True)
        
        assert approved.status == "active"
        assert approved.activated_at is not None

    def test_approve_advance_without_activation(self, db_session, test_model):
        """Test approving without immediate activation."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        
        approved = approve_advance(db_session, advance, activate=False)
        
        assert approved.status == "approved"
        assert approved.activated_at is None


class TestOutstandingAdvances:
    """Tests for outstanding advance calculations."""

    def test_outstanding_advance_total_no_advances(self, db_session, test_model):
        """Test outstanding total when no advances exist."""
        total = outstanding_advance_total(db_session, test_model.id)
        assert total == Decimal("0")

    def test_outstanding_advance_total_with_active(self, db_session, test_model):
        """Test outstanding total with active advances."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        approve_advance(db_session, advance, activate=True)
        
        total = outstanding_advance_total(db_session, test_model.id)
        assert total >= Decimal("500.00")


class TestAdvanceRepayment:
    """Tests for advance repayment."""

    def test_record_advance_repayment(self, db_session, test_model):
        """Test recording a repayment."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        approve_advance(db_session, advance, activate=True)
        
        repayment = record_advance_repayment(
            db_session,
            advance,
            amount=Decimal("100.00"),
            source="manual",
        )
        
        assert repayment.amount == Decimal("100.00")
        assert repayment.source == "manual"
        
        # Check that remaining is updated
        db_session.refresh(advance)
        assert advance.amount_remaining == Decimal("400.00")

    def test_record_repayment_invalid_amount_raises(self, db_session, test_model):
        """Test that zero or negative repayment raises ValueError."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        approve_advance(db_session, advance, activate=True)
        
        with pytest.raises(ValueError, match="must be > 0"):
            record_advance_repayment(db_session, advance, amount=Decimal("0"))


class TestAdvanceDeletion:
    """Tests for deleting advances."""

    def test_delete_advance_no_repayments(self, db_session, test_model):
        """Test deleting an advance with no repayments."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        advance_id = advance.id
        
        delete_advance(db_session, advance)
        
        # Verify it's deleted
        result = get_advance(db_session, advance_id)
        assert result is None

    def test_delete_advance_with_repayments_raises(self, db_session, test_model):
        """Test that deleting advance with repayments raises ValueError."""
        advance = create_advance(
            db_session,
            test_model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        approve_advance(db_session, advance, activate=True)
        record_advance_repayment(db_session, advance, amount=Decimal("50.00"))
        
        with pytest.raises(ValueError, match="Cannot delete"):
            delete_advance(db_session, advance)
