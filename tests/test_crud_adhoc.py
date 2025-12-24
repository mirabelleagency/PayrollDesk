"""Tests for adhoc payments and additional CRUD functions."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_model,
    list_adhoc_payments,
    list_adhoc_payments_for_month,
    get_adhoc_payment,
    create_adhoc_payment,
    update_adhoc_payment,
    delete_adhoc_payment,
    delete_model,
    update_model,
)
from app.models import AdhocPayment
from app.schemas import ModelCreate, AdhocPaymentCreate, AdhocPaymentUpdate


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
    """Create a model for adhoc payment tests."""
    payload = ModelCreate(
        code="ADHOC001",
        real_name="Adhoc Test Model",
        working_name="Adhoc Test",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("2000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


class TestAdhocPayments:
    """Tests for adhoc payment CRUD operations."""

    def test_create_adhoc_payment(self, db_session, test_model):
        """Test creating an adhoc payment."""
        payload = AdhocPaymentCreate(
            pay_date=date(2024, 6, 15),
            amount=Decimal("250.00"),
            description="Bonus payment",
            notes=None,
        )
        payment = create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        assert payment.id is not None
        assert payment.model_id == test_model.id
        assert payment.amount == Decimal("250.00")
        assert payment.status == "pending"

    def test_get_adhoc_payment(self, db_session, test_model):
        """Test getting an adhoc payment by ID."""
        payload = AdhocPaymentCreate(
            pay_date=date(2024, 7, 1),
            amount=Decimal("150.00"),
            notes=None,
        )
        payment = create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        result = get_adhoc_payment(db_session, payment.id)
        
        assert result is not None
        assert result.id == payment.id

    def test_get_adhoc_payment_not_found(self, db_session):
        """Test getting non-existent adhoc payment."""
        result = get_adhoc_payment(db_session, 999999)
        assert result is None

    def test_list_adhoc_payments_for_model(self, db_session, test_model):
        """Test listing adhoc payments for a model."""
        for i in range(2):
            payload = AdhocPaymentCreate(
                pay_date=date(2024, 8, 1 + i),
                amount=Decimal("100.00") + Decimal(i * 100),
                notes=None,
            )
            create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        payments = list_adhoc_payments(db_session, test_model.id)
        
        assert len(payments) >= 2

    def test_list_adhoc_payments_with_status_filter(self, db_session, test_model):
        """Test listing adhoc payments filtered by status."""
        payload = AdhocPaymentCreate(
            pay_date=date(2024, 9, 1),
            amount=Decimal("100.00"),
            notes=None,
        )
        create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        pending = list_adhoc_payments(db_session, test_model.id, status="pending")
        assert len(pending) >= 1

    def test_list_adhoc_payments_for_month(self, db_session, test_model):
        """Test listing adhoc payments for a specific month."""
        payload = AdhocPaymentCreate(
            pay_date=date(2099, 3, 15),  # Future date to isolate test
            amount=Decimal("100.00"),
            notes=None,
        )
        create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        payments = list_adhoc_payments_for_month(db_session, year=2099, month=3)
        
        assert len(payments) >= 1

    def test_list_adhoc_payments_for_month_invalid_raises(self, db_session):
        """Test that invalid month raises ValueError."""
        with pytest.raises(ValueError, match="month must be"):
            list_adhoc_payments_for_month(db_session, year=2024, month=0)
        
        with pytest.raises(ValueError, match="month must be"):
            list_adhoc_payments_for_month(db_session, year=2024, month=13)

    def test_update_adhoc_payment(self, db_session, test_model):
        """Test updating an adhoc payment."""
        payload = AdhocPaymentCreate(
            pay_date=date(2024, 10, 1),
            amount=Decimal("100.00"),
            notes=None,
        )
        payment = create_adhoc_payment(db_session, model=test_model, payload=payload)
        
        update_payload = AdhocPaymentUpdate(
            amount=Decimal("150.00"),
            status="paid",
        )
        updated = update_adhoc_payment(db_session, payment, update_payload)
        
        assert updated.amount == Decimal("150.00")
        assert updated.status == "paid"

    def test_delete_adhoc_payment(self, db_session, test_model):
        """Test deleting an adhoc payment."""
        payload = AdhocPaymentCreate(
            pay_date=date(2024, 11, 1),
            amount=Decimal("100.00"),
            notes=None,
        )
        payment = create_adhoc_payment(db_session, model=test_model, payload=payload)
        payment_id = payment.id
        
        delete_adhoc_payment(db_session, payment)
        
        result = get_adhoc_payment(db_session, payment_id)
        assert result is None


class TestModelUpdateDelete:
    """Tests for model update and delete operations."""

    def test_delete_model_hard(self, db_session):
        """Test hard deleting a model."""
        # Create a model specifically for deletion
        payload = ModelCreate(
            code="DELETE001",
            real_name="To Delete",
            working_name="Delete Me",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
        )
        model = create_model(db_session, payload)
        model_id = model.id
        
        delete_model(db_session, model)
        
        # Verify it's gone
        from app.crud import get_model
        result = get_model(db_session, model_id)
        assert result is None
