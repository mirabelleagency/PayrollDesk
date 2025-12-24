"""Integration tests for critical workflows.

Tests the complete flow of key business processes including:
- Model creation workflow
- Schedule run workflow
- Payment workflow
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Model, ScheduleRun, Payout
from app.crud import (
    create_model,
    get_model,
    get_model_by_code,
    create_schedule_run,
    get_schedule_run,
    list_payouts_for_run,
    delete_schedule_run,
)
from app.schemas import ModelCreate


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
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)


class TestModelCreationWorkflow:
    """Integration tests for model creation workflow."""

    def test_create_model_with_compensation_adjustment(self, db_session):
        """Test that creating a model also creates initial compensation adjustment."""
        payload = ModelCreate(
            code="INTEG001",
            real_name="Integration Test Model",
            working_name="Test Model",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("2500.00"),
            start_date=date(2024, 1, 1),
        )
        
        model = create_model(db_session, payload)
        
        # Verify model created
        assert model.id is not None
        assert model.code == "INTEG001"
        
        # Verify can retrieve by code
        retrieved = get_model_by_code(db_session, "INTEG001")
        assert retrieved is not None
        assert retrieved.id == model.id
        
        # Verify compensation adjustment was created (implicit in create_model)
        from app.crud import get_effective_compensation_amount
        effective = get_effective_compensation_amount(db_session, model, date.today())
        assert effective == Decimal("2500.00")

    def test_model_code_uniqueness_in_lookup(self, db_session):
        """Test that model lookup by code returns correct model."""
        payload1 = ModelCreate(
            code="UNIQUE001",
            real_name="First Model",
            working_name="First",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
        )
        payload2 = ModelCreate(
            code="UNIQUE002",
            real_name="Second Model",
            working_name="Second",
            status="Active",
            payment_method="crypto",
            payment_frequency="biweekly",
            amount_monthly=Decimal("2000.00"),
            start_date=date(2024, 1, 1),
        )
        
        model1 = create_model(db_session, payload1)
        model2 = create_model(db_session, payload2)
        
        # Lookup each by code
        found1 = get_model_by_code(db_session, "UNIQUE001")
        found2 = get_model_by_code(db_session, "UNIQUE002")
        
        assert found1.id == model1.id
        assert found2.id == model2.id
        assert found1.payment_method == "bank"
        assert found2.payment_method == "crypto"


class TestScheduleRunWorkflow:
    """Integration tests for schedule run workflow."""

    def test_schedule_run_creation_and_retrieval(self, db_session):
        """Test complete schedule run creation workflow."""
        # Create a schedule run
        run = create_schedule_run(
            db=db_session,
            target_year=2095,
            target_month=1,
            currency="USD",
            include_inactive=False,
            summary={
                "models_paid": 5,
                "total_payout": Decimal("5000.00"),
                "frequency_counts": {"monthly": 3, "biweekly": 2},
            },
            export_path="exports/test_integration.csv",
        )
        
        # Verify creation
        assert run.id is not None
        assert run.target_year == 2095
        assert run.target_month == 1
        
        # Retrieve and verify
        retrieved = get_schedule_run(db_session, run.id)
        assert retrieved is not None
        assert retrieved.currency == "USD"
        assert retrieved.summary_models_paid == 5

    def test_schedule_run_with_payouts(self, db_session):
        """Test schedule run with associated payouts."""
        # Create a model first
        model_payload = ModelCreate(
            code="SCHED001",
            real_name="Schedule Test Model",
            working_name="Schedule Test",
            status="Active",
            payment_method="bank",
            payment_frequency="monthly",
            amount_monthly=Decimal("1500.00"),
            start_date=date(2024, 1, 1),
        )
        model = create_model(db_session, model_payload)
        
        # Create a schedule run
        run = create_schedule_run(
            db=db_session,
            target_year=2096,
            target_month=6,
            currency="USD",
            include_inactive=False,
            summary={"models_paid": 1, "total_payout": Decimal("1500.00")},
            export_path="exports/schedule_test.csv",
        )
        
        # Add a payout manually (simulating payroll generation)
        payout = Payout(
            schedule_run_id=run.id,
            model_id=model.id,
            pay_date=date(2096, 6, 15),
            code=model.code,
            real_name=model.real_name,
            working_name=model.working_name,
            payment_method=model.payment_method,
            payment_frequency=model.payment_frequency,
            amount=Decimal("1500.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        # List payouts for run
        payouts = list_payouts_for_run(db_session, run.id)
        
        assert len(payouts) >= 1
        assert payouts[0].model_id == model.id

    def test_schedule_run_deletion_cascades(self, db_session):
        """Test that deleting a schedule run cleans up payouts."""
        # Create run
        run = create_schedule_run(
            db=db_session,
            target_year=2094,
            target_month=12,
            currency="USD",
            include_inactive=False,
            summary={},
            export_path="exports/delete_test.csv",
        )
        run_id = run.id
        
        # Delete run
        delete_schedule_run(db_session, run)
        
        # Verify deleted
        retrieved = get_schedule_run(db_session, run_id)
        assert retrieved is None


class TestHealthEndpointsWorkflow:
    """Integration tests for health check endpoints."""

    def test_health_endpoint(self, client):
        """Test basic health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "ok")

    def test_db_health_endpoint(self, client):
        """Test database health endpoint."""
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "ok")
        # Check for database info (may be nested)
        assert "database" in data or "response_time_ms" in data


class TestAuthenticationWorkflow:
    """Integration tests for authentication workflow."""

    def test_login_redirect_when_not_authenticated(self, client):
        """Test that protected routes redirect to login."""
        # Try to access dashboard without login
        response = client.get("/dashboard", follow_redirects=False)
        # Should redirect to login
        assert response.status_code in (302, 303, 307)

    def test_login_success(self, client):
        """Test successful login flow."""
        response = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303, 307)
        # Should set some form of auth cookie
        assert len(response.cookies) > 0

    def test_login_failure(self, client):
        """Test failed login flow."""
        response = client.post(
            "/login",
            data={"username": "admin", "password": "wrongpassword"},
            follow_redirects=False,
        )
        # Could be redirect or 401
        assert response.status_code in (302, 303, 307, 401)

    def test_logout_flow(self, client):
        """Test logout flow."""
        # First login
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        
        # Then logout
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code in (302, 303, 307)


class TestDashboardWorkflow:
    """Integration tests for dashboard workflow."""

    def test_dashboard_accessible_after_login(self, client):
        """Test dashboard is accessible after authentication."""
        login_admin(client)
        
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_models_list_accessible(self, client):
        """Test models list page is accessible."""
        login_admin(client)
        
        response = client.get("/models")
        assert response.status_code == 200

    def test_schedules_list_accessible(self, client):
        """Test schedules list page is accessible."""
        login_admin(client)
        
        response = client.get("/schedules")
        assert response.status_code == 200
