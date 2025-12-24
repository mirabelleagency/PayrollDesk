"""Tests for core CRUD operations to improve coverage."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    count_models,
    count_models_by_frequency,
    count_models_by_payment_method,
    create_model,
    get_model,
    get_model_by_code,
    list_models,
    sum_paid_for_models,
    list_payment_methods,
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
def sample_models(db_session: Session):
    """Create several models with different attributes for testing."""
    models = []
    configs = [
        ("MOD001", "Active", "bank", "monthly"),
        ("MOD002", "Active", "bank", "biweekly"),
        ("MOD003", "Inactive", "crypto", "monthly"),
        ("MOD004", "Active", "crypto", "monthly"),
        ("MOD005", "Inactive", "bank", "weekly"),
    ]
    
    for code, status, payment_method, frequency in configs:
        payload = ModelCreate(
            code=code,
            real_name=f"{code} Real",
            working_name=f"{code} Working",
            status=status,
            payment_method=payment_method,
            payment_frequency=frequency,
            amount_monthly=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
        )
        models.append(create_model(db_session, payload))
    
    return models


class TestListModelsFiltering:
    """Tests for list_models with various filters."""

    def test_list_models_no_filter(self, db_session, sample_models):
        """Test listing all models without filters."""
        result = list_models(db_session)
        # Should include at least our sample models
        codes = [m.code for m in result]
        for model in sample_models:
            assert model.code in codes

    def test_list_models_filter_by_status(self, db_session, sample_models):
        """Test filtering models by status."""
        active = list_models(db_session, status="Active")
        inactive = list_models(db_session, status="Inactive")
        
        active_codes = [m.code for m in active]
        inactive_codes = [m.code for m in inactive]
        
        assert "MOD001" in active_codes
        assert "MOD003" in inactive_codes
        assert "MOD003" not in active_codes

    def test_list_models_filter_by_frequency(self, db_session, sample_models):
        """Test filtering models by payment frequency."""
        monthly = list_models(db_session, frequency="monthly")
        monthly_codes = [m.code for m in monthly]
        
        assert "MOD001" in monthly_codes
        assert "MOD003" in monthly_codes
        assert "MOD004" in monthly_codes
        assert "MOD002" not in monthly_codes  # bi-weekly

    def test_list_models_filter_by_payment_method(self, db_session, sample_models):
        """Test filtering models by payment method."""
        bank = list_models(db_session, payment_method="bank")
        bank_codes = [m.code for m in bank]
        
        assert "MOD001" in bank_codes
        assert "MOD002" in bank_codes
        assert "MOD003" not in bank_codes  # crypto

    def test_list_models_combined_filters(self, db_session, sample_models):
        """Test combining multiple filters."""
        result = list_models(
            db_session,
            status="Active",
            frequency="monthly",
            payment_method="crypto"
        )
        codes = [m.code for m in result]
        
        # Only MOD004 matches all criteria
        assert "MOD004" in codes
        assert "MOD001" not in codes  # Active, monthly, but bank
        assert "MOD003" not in codes  # Inactive

    def test_list_models_filter_by_code(self, db_session, sample_models):
        """Test filtering models by code substring."""
        result = list_models(db_session, code="MOD00")
        codes = [m.code for m in result]
        
        # All our sample models should match
        for model in sample_models:
            assert model.code in codes

    def test_list_models_with_limit(self, db_session, sample_models):
        """Test limiting results."""
        result = list_models(db_session, limit=2)
        assert len(result) == 2

    def test_list_models_with_offset(self, db_session, sample_models):
        """Test offset pagination."""
        all_models = list_models(db_session)
        offset_models = list_models(db_session, offset=2)
        
        # Offset models should skip first 2
        assert len(offset_models) == len(all_models) - 2


class TestCountModels:
    """Tests for count_models with filters."""

    def test_count_all_models(self, db_session, sample_models):
        """Test counting all models."""
        count = count_models(db_session)
        assert count >= 5  # At least our sample models

    def test_count_models_by_status(self, db_session, sample_models):
        """Test counting models by status."""
        active_count = count_models(db_session, status="Active")
        inactive_count = count_models(db_session, status="Inactive")
        
        assert active_count >= 3  # MOD001, MOD002, MOD004
        assert inactive_count >= 2  # MOD003, MOD005

    def test_count_models_by_frequency(self, db_session, sample_models):
        """Test counting models by frequency."""
        monthly_count = count_models(db_session, frequency="monthly")
        assert monthly_count >= 3  # MOD001, MOD003, MOD004


class TestCountModelsByGroups:
    """Tests for count_models_by_payment_method and count_models_by_frequency."""

    def test_count_models_by_payment_method(self, db_session, sample_models):
        """Test grouping counts by payment method."""
        counts = count_models_by_payment_method(db_session)
        
        assert "bank" in counts
        assert "crypto" in counts
        assert counts["bank"] >= 3  # MOD001, MOD002, MOD005
        assert counts["crypto"] >= 2  # MOD003, MOD004

    def test_count_models_by_frequency_grouped(self, db_session, sample_models):
        """Test grouping counts by frequency."""
        counts = count_models_by_frequency(db_session)
        
        assert "monthly" in counts
        assert counts["monthly"] >= 3


class TestGetModelFunctions:
    """Tests for get_model and get_model_by_code."""

    def test_get_model_by_id(self, db_session, sample_models):
        """Test getting a model by ID."""
        model = sample_models[0]
        result = get_model(db_session, model.id)
        
        assert result is not None
        assert result.id == model.id
        assert result.code == model.code

    def test_get_model_by_id_not_found(self, db_session):
        """Test getting a non-existent model by ID."""
        result = get_model(db_session, 999999)
        assert result is None

    def test_get_model_by_code(self, db_session, sample_models):
        """Test getting a model by code."""
        result = get_model_by_code(db_session, "MOD001")
        
        assert result is not None
        assert result.code == "MOD001"

    def test_get_model_by_code_not_found(self, db_session):
        """Test getting a non-existent model by code."""
        result = get_model_by_code(db_session, "NONEXISTENT999")
        assert result is None


class TestListPaymentMethods:
    """Tests for list_payment_methods."""

    def test_list_payment_methods(self, db_session, sample_models):
        """Test listing distinct payment methods."""
        methods = list_payment_methods(db_session)
        
        assert "bank" in methods
        assert "crypto" in methods


class TestSumPaidForModels:
    """Tests for sum_paid_for_models."""

    def test_sum_paid_for_models_empty(self, db_session, sample_models):
        """Test sum when no payouts exist."""
        # With fresh models, no payouts should exist
        result = sum_paid_for_models(db_session)
        assert isinstance(result, Decimal)
        # Could be 0 or include previous test data

    def test_sum_paid_with_status_filter(self, db_session, sample_models):
        """Test sum with status filter."""
        result = sum_paid_for_models(db_session, status="Active")
        assert isinstance(result, Decimal)
