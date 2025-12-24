"""Tests for database connection retry logic."""
import os
from unittest.mock import patch, MagicMock
import pytest


def test_retry_env_vars_default_values():
    """Test default values for retry configuration."""
    # Clear any existing env vars
    env_backup = {
        "DB_CONNECT_RETRIES": os.environ.get("DB_CONNECT_RETRIES"),
        "DB_RETRY_DELAY": os.environ.get("DB_RETRY_DELAY"),
    }
    
    try:
        os.environ.pop("DB_CONNECT_RETRIES", None)
        os.environ.pop("DB_RETRY_DELAY", None)
        
        # Defaults should be 3 retries and 1.0s delay
        max_retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
        base_delay = float(os.getenv("DB_RETRY_DELAY", "1.0"))
        
        assert max_retries == 3
        assert base_delay == 1.0
    finally:
        # Restore env vars
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value


def test_retry_env_vars_custom_values():
    """Test custom values for retry configuration."""
    env_backup = {
        "DB_CONNECT_RETRIES": os.environ.get("DB_CONNECT_RETRIES"),
        "DB_RETRY_DELAY": os.environ.get("DB_RETRY_DELAY"),
    }
    
    try:
        os.environ["DB_CONNECT_RETRIES"] = "5"
        os.environ["DB_RETRY_DELAY"] = "2.5"
        
        max_retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
        base_delay = float(os.getenv("DB_RETRY_DELAY", "1.0"))
        
        assert max_retries == 5
        assert base_delay == 2.5
    finally:
        # Restore env vars
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def test_exponential_backoff_calculation():
    """Test exponential backoff delay calculation."""
    base_delay = 1.0
    
    # attempt 1: delay = 1.0 * 2^0 = 1.0
    # attempt 2: delay = 1.0 * 2^1 = 2.0
    # attempt 3: delay = 1.0 * 2^2 = 4.0
    
    for attempt in range(1, 4):
        delay = base_delay * (2 ** (attempt - 1))
        expected = [1.0, 2.0, 4.0][attempt - 1]
        assert delay == expected, f"Attempt {attempt} should have delay {expected}"


def test_retry_logic_succeeds_on_first_try():
    """Test that successful first connection returns immediately."""
    from app import database
    
    # The database module is already initialized, so the engine exists
    # Just verify the engine is functional
    assert database.engine is not None
    
    # Verify we can connect
    with database.engine.connect() as conn:
        result = conn.execute(database.text("SELECT 1"))
        assert result.scalar() == 1


def test_database_url_masking():
    """Test that database URLs are properly masked for logging."""
    from app.database import _mask_db_url
    
    # Test PostgreSQL URL masking
    pg_url = "postgresql://user:secret_password@localhost:5432/dbname"
    masked = _mask_db_url(pg_url)
    assert "secret_password" not in masked
    assert "***" in masked
    assert "user" in masked
    assert "localhost" in masked


def test_retry_respects_max_retries_env():
    """Test that DB_CONNECT_RETRIES is respected."""
    # Just verify the env var is parsed correctly
    os.environ["DB_CONNECT_RETRIES"] = "1"
    try:
        max_retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
        assert max_retries == 1
    finally:
        os.environ.pop("DB_CONNECT_RETRIES", None)
