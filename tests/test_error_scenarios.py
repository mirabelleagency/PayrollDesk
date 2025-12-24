"""Error scenario tests for user-facing features.

Tests validation errors, edge cases, and error handling.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.schemas import ModelCreate, AdhocPaymentCreate
from app.crud import create_model, get_schedule_run, get_model


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Provide a test client for HTTP tests."""
    return TestClient(app)


def login_admin(client: TestClient) -> None:
    """Login as admin user."""
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)


class TestModelValidationErrors:
    """Tests for model creation/update validation errors."""

    def test_model_create_invalid_status(self, db_session):
        """Test that invalid status is rejected."""
        with pytest.raises(ValueError, match="(?i)status"):
            ModelCreate(
                code="ERR001",
                real_name="Error Test",
                working_name="Error",
                status="InvalidStatus",  # Invalid
                payment_method="bank",
                payment_frequency="monthly",
                amount_monthly=Decimal("1000.00"),
                start_date=date(2024, 1, 1),
            )

    def test_model_create_invalid_frequency(self, db_session):
        """Test that invalid payment frequency is rejected."""
        with pytest.raises(ValueError, match="(?i)frequency"):
            ModelCreate(
                code="ERR002",
                real_name="Error Test",
                working_name="Error",
                status="Active",
                payment_method="bank",
                payment_frequency="invalid_frequency",  # Invalid
                amount_monthly=Decimal("1000.00"),
                start_date=date(2024, 1, 1),
            )

    def test_model_create_missing_required_fields(self, db_session):
        """Test that missing required fields are rejected."""
        with pytest.raises(Exception):  # Pydantic validation error
            ModelCreate(
                code="ERR003",
                # Missing real_name, working_name, etc.
            )

    def test_model_create_negative_amount(self, db_session):
        """Test that negative amount is rejected."""
        with pytest.raises(ValueError):
            ModelCreate(
                code="ERR004",
                real_name="Error Test",
                working_name="Error",
                status="Active",
                payment_method="bank",
                payment_frequency="monthly",
                amount_monthly=Decimal("-100.00"),  # Negative
                start_date=date(2024, 1, 1),
            )


class TestAdhocPaymentValidationErrors:
    """Tests for adhoc payment validation errors."""

    def test_adhoc_payment_invalid_status(self, db_session):
        """Test that invalid adhoc payment status is rejected."""
        with pytest.raises(ValueError, match="(?i)status"):
            AdhocPaymentCreate(
                pay_date=date(2024, 6, 15),
                amount=Decimal("100.00"),
                notes=None,
                status="invalid_status",  # Invalid
            )

    def test_adhoc_payment_zero_amount(self, db_session):
        """Test that zero amount is rejected."""
        with pytest.raises(ValueError):
            AdhocPaymentCreate(
                pay_date=date(2024, 6, 15),
                amount=Decimal("0.00"),  # Zero is invalid
                notes=None,
            )

    def test_adhoc_payment_negative_amount(self, db_session):
        """Test that negative amount is rejected."""
        with pytest.raises(ValueError):
            AdhocPaymentCreate(
                pay_date=date(2024, 6, 15),
                amount=Decimal("-50.00"),  # Negative
                notes=None,
            )


class TestAPIErrorHandling:
    """Tests for API error handling."""

    def test_get_nonexistent_schedule(self, client):
        """Test that requesting non-existent schedule returns 404."""
        login_admin(client)
        
        response = client.get("/schedules/999999")
        assert response.status_code == 404

    def test_get_nonexistent_model(self, client):
        """Test that requesting non-existent model returns 404."""
        login_admin(client)
        
        response = client.get("/models/999999")
        assert response.status_code == 404

    def test_unauthorized_access(self, client):
        """Test that unauthorized access is blocked."""
        # Don't login - should be redirected
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (302, 303, 307, 401)

    def test_invalid_login_credentials(self, client):
        """Test that invalid credentials are rejected."""
        response = client.post(
            "/login",
            data={"username": "nonexistent", "password": "badpassword"},
        )
        # Should not succeed
        assert response.status_code in (401, 302, 303)  # Error or redirect back


class TestCRUDErrorHandling:
    """Tests for CRUD error handling."""

    def test_get_nonexistent_model_returns_none(self, db_session):
        """Test that getting non-existent model returns None."""
        result = get_model(db_session, 999999)
        assert result is None

    def test_get_nonexistent_schedule_returns_none(self, db_session):
        """Test that getting non-existent schedule returns None."""
        result = get_schedule_run(db_session, 999999)
        assert result is None


class TestAdvanceValidationErrors:
    """Tests for advance creation validation errors."""

    def test_advance_invalid_strategy(self, db_session):
        """Test that invalid advance strategy is rejected."""
        from app.crud import create_advance
        
        # Create a model for the test
        payload = ModelCreate(
            code="ADVERR001",
            real_name="Advance Error Test",
            working_name="Advance Error",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("2000.00"),
            start_date=date(2024, 1, 1),
        )
        model = create_model(db_session, payload)
        
        with pytest.raises(ValueError, match="strategy"):
            create_advance(
                db_session,
                model,
                amount_total=Decimal("500.00"),
                strategy="invalid",  # Invalid strategy
            )

    def test_advance_fixed_without_amount(self, db_session):
        """Test that fixed strategy without amount is rejected."""
        from app.crud import create_advance
        
        payload = ModelCreate(
            code="ADVERR002",
            real_name="Advance Error Test 2",
            working_name="Advance Error 2",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("2000.00"),
            start_date=date(2024, 1, 1),
        )
        model = create_model(db_session, payload)
        
        with pytest.raises(ValueError, match="fixed_amount"):
            create_advance(
                db_session,
                model,
                amount_total=Decimal("500.00"),
                strategy="fixed",
                fixed_amount=None,  # Missing required amount
            )

    def test_advance_repayment_zero_amount(self, db_session):
        """Test that zero repayment amount is rejected."""
        from app.crud import create_advance, approve_advance, record_advance_repayment
        
        payload = ModelCreate(
            code="ADVERR003",
            real_name="Advance Error Test 3",
            working_name="Advance Error 3",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("2000.00"),
            start_date=date(2024, 1, 1),
        )
        model = create_model(db_session, payload)
        
        advance = create_advance(
            db_session,
            model,
            amount_total=Decimal("500.00"),
            strategy="fixed",
            fixed_amount=Decimal("50.00"),
        )
        approve_advance(db_session, advance, activate=True)
        
        with pytest.raises(ValueError, match="must be > 0"):
            record_advance_repayment(db_session, advance, amount=Decimal("0"))


class TestScheduleRunValidationErrors:
    """Tests for schedule run validation errors."""

    def test_duplicate_schedule_run_raises(self, db_session):
        """Test that creating duplicate schedule run raises error."""
        from app.crud import create_schedule_run
        
        # Create first run
        create_schedule_run(
            db=db_session,
            target_year=2090,
            target_month=1,
            currency="USD",
            include_inactive=False,
            summary={},
            export_path="exports/dup_test.csv",
        )
        
        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            create_schedule_run(
                db=db_session,
                target_year=2090,
                target_month=1,
                currency="USD",
                include_inactive=False,
                summary={},
                export_path="exports/dup_test2.csv",
            )


class TestAdhocPaymentMonthValidation:
    """Tests for adhoc payment month validation."""

    def test_list_adhoc_invalid_month_zero(self, db_session):
        """Test that month=0 raises ValueError."""
        from app.crud import list_adhoc_payments_for_month
        
        with pytest.raises(ValueError, match="month must be"):
            list_adhoc_payments_for_month(db_session, year=2024, month=0)

    def test_list_adhoc_invalid_month_13(self, db_session):
        """Test that month=13 raises ValueError."""
        from app.crud import list_adhoc_payments_for_month
        
        with pytest.raises(ValueError, match="month must be"):
            list_adhoc_payments_for_month(db_session, year=2024, month=13)

    def test_list_adhoc_valid_months(self, db_session):
        """Test that valid months work correctly."""
        from app.crud import list_adhoc_payments_for_month
        
        # All valid months should work
        for month in range(1, 13):
            result = list_adhoc_payments_for_month(db_session, year=2024, month=month)
            assert isinstance(result, (list, tuple)) or hasattr(result, '__iter__')
