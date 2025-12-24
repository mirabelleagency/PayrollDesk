"""Tests for Model soft delete functionality."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_model,
    delete_model,
    get_deleted_model,
    get_model,
    list_deleted_models,
    list_models,
    restore_model,
    soft_delete_model,
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
def test_model(db_session: Session):
    """Create a test model for soft delete tests."""
    payload = ModelCreate(
        code="SOFTDEL001",
        real_name="Soft Delete Test",
        working_name="Test Model",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


class TestSoftDelete:
    """Tests for soft_delete_model function."""

    def test_soft_delete_sets_deleted_at(self, db_session, test_model):
        """Test that soft delete sets deleted_at timestamp."""
        assert test_model.deleted_at is None
        
        soft_delete_model(db_session, test_model)
        
        assert test_model.deleted_at is not None

    def test_soft_deleted_model_excluded_from_list(self, db_session, test_model):
        """Test that soft-deleted models are excluded from list_models."""
        # Model should be in list before soft delete
        models_before = list_models(db_session)
        assert any(m.id == test_model.id for m in models_before)
        
        # Soft delete the model
        soft_delete_model(db_session, test_model)
        
        # Model should not be in list after soft delete
        models_after = list_models(db_session)
        assert not any(m.id == test_model.id for m in models_after)

    def test_soft_deleted_model_included_with_flag(self, db_session, test_model):
        """Test that soft-deleted models are included when include_deleted=True."""
        soft_delete_model(db_session, test_model)
        
        # Should not be in default list
        models_default = list_models(db_session)
        assert not any(m.id == test_model.id for m in models_default)
        
        # Should be in list when include_deleted=True
        models_with_deleted = list_models(db_session, include_deleted=True)
        assert any(m.id == test_model.id for m in models_with_deleted)


class TestRestoreModel:
    """Tests for restore_model function."""

    def test_restore_clears_deleted_at(self, db_session, test_model):
        """Test that restore clears deleted_at timestamp."""
        soft_delete_model(db_session, test_model)
        assert test_model.deleted_at is not None
        
        restore_model(db_session, test_model)
        
        assert test_model.deleted_at is None

    def test_restored_model_appears_in_list(self, db_session, test_model):
        """Test that restored model appears in list_models again."""
        soft_delete_model(db_session, test_model)
        
        # Verify not in list
        models_deleted = list_models(db_session)
        assert not any(m.id == test_model.id for m in models_deleted)
        
        # Restore and verify in list
        restore_model(db_session, test_model)
        models_restored = list_models(db_session)
        assert any(m.id == test_model.id for m in models_restored)


class TestListDeletedModels:
    """Tests for list_deleted_models function."""

    def test_list_deleted_models_returns_only_deleted(self, db_session, test_model):
        """Test that list_deleted_models returns only soft-deleted models."""
        # Before soft delete, should not be in deleted list
        deleted_before = list_deleted_models(db_session)
        assert not any(m.id == test_model.id for m in deleted_before)
        
        # Soft delete
        soft_delete_model(db_session, test_model)
        
        # Should now be in deleted list
        deleted_after = list_deleted_models(db_session)
        assert any(m.id == test_model.id for m in deleted_after)


class TestGetDeletedModel:
    """Tests for get_deleted_model function."""

    def test_get_deleted_model_returns_soft_deleted(self, db_session, test_model):
        """Test that get_deleted_model returns soft-deleted model."""
        model_id = test_model.id
        
        # Before soft delete, should return None
        assert get_deleted_model(db_session, model_id) is None
        
        # Soft delete
        soft_delete_model(db_session, test_model)
        
        # Should now return the model
        deleted = get_deleted_model(db_session, model_id)
        assert deleted is not None
        assert deleted.id == model_id

    def test_get_deleted_model_returns_none_for_active(self, db_session, test_model):
        """Test that get_deleted_model returns None for active models."""
        result = get_deleted_model(db_session, test_model.id)
        assert result is None


class TestHardDeleteVsSoftDelete:
    """Tests comparing hard delete vs soft delete behavior."""

    def test_hard_delete_removes_permanently(self, db_session, test_model):
        """Test that hard delete permanently removes the model."""
        model_id = test_model.id
        
        delete_model(db_session, test_model)
        
        # Should not be found anywhere
        assert get_model(db_session, model_id) is None
        assert get_deleted_model(db_session, model_id) is None

    def test_soft_delete_preserves_data(self, db_session, test_model):
        """Test that soft delete preserves model data."""
        model_id = test_model.id
        original_code = test_model.code
        
        soft_delete_model(db_session, test_model)
        
        # Should still be accessible via include_deleted
        models = list_models(db_session, include_deleted=True)
        found = next((m for m in models if m.id == model_id), None)
        
        assert found is not None
        assert found.code == original_code
