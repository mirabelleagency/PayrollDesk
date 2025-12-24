"""Tests for health check endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for /health and /health/db endpoints."""

    def test_health_basic(self, client):
        """Test basic /health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_db_returns_healthy(self, client):
        """Test /health/db endpoint returns healthy status with database info."""
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "database" in data
        assert data["database"]["connected"] is True
        assert "response_time_ms" in data["database"]
        assert isinstance(data["database"]["response_time_ms"], (int, float))
        assert data["database"]["engine"] in ("postgresql", "sqlite")

    def test_health_db_response_time_is_reasonable(self, client):
        """Test that database response time is within reasonable bounds."""
        response = client.get("/health/db")
        data = response.json()
        
        # Response time should be less than 1 second for a simple SELECT 1
        assert data["database"]["response_time_ms"] < 1000
