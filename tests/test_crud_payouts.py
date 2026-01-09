"""Tests for Payout and ScheduleRun CRUD operations."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_model,
    create_schedule_run,
    delete_schedule_run,
    get_payout,
    get_schedule_run,
    list_payouts_for_run,
    list_schedule_runs,
    frequencies_for_run,
    payment_methods_for_run,
    payout_status_counts,
    payout_codes_for_run,
    payout_dates_for_run,
    run_payment_summary,
    total_paid_by_model,
    list_payouts_for_model,
)
from app.models import Payout, ScheduleRun
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
    """Create a model for payout tests."""
    payload = ModelCreate(
        code="PAYTEST001",
        real_name="Payout Test Model",
        working_name="Payout Test",
        status="Active",
        payment_method="bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
        start_date=date(2024, 1, 1),
    )
    return create_model(db_session, payload)


@pytest.fixture
def schedule_run(db_session: Session):
    """Create a schedule run for tests."""
    # Use a unique year/month to avoid conflicts with existing data
    run = create_schedule_run(
        db=db_session,
        target_year=2099,
        target_month=1,
        currency="USD",
        include_inactive=False,
        summary={"models_paid": 0, "total_payout": Decimal("0.00"), "frequency_counts": {}},
        export_path="exports/test_schedule.csv",
    )
    return run


class TestScheduleRunCrud:
    """Tests for ScheduleRun CRUD operations."""

    def test_create_schedule_run(self, db_session):
        """Test creating a schedule run."""
        run = create_schedule_run(
            db=db_session,
            target_year=2098,
            target_month=6,
            currency="USD",
            include_inactive=True,
            summary={
                "models_paid": 5,
                "total_payout": Decimal("5000.00"),
                "frequency_counts": {"monthly": 3, "biweekly": 2},
            },
            export_path="exports/test_run.csv",
        )
        
        assert run.id is not None
        assert run.target_year == 2098
        assert run.target_month == 6
        assert run.currency == "USD"
        assert run.include_inactive is True
        assert run.summary_models_paid == 5

    def test_create_schedule_run_duplicate_raises(self, db_session, schedule_run):
        """Test that duplicate schedule run raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            create_schedule_run(
                db=db_session,
                target_year=schedule_run.target_year,
                target_month=schedule_run.target_month,
                currency="USD",
                include_inactive=False,
                summary={},
                export_path="exports/duplicate.csv",
            )

    def test_get_schedule_run(self, db_session, schedule_run):
        """Test getting a schedule run by ID."""
        result = get_schedule_run(db_session, schedule_run.id)
        
        assert result is not None
        assert result.id == schedule_run.id

    def test_get_schedule_run_not_found(self, db_session):
        """Test getting a non-existent schedule run."""
        result = get_schedule_run(db_session, 999999)
        assert result is None

    def test_list_schedule_runs(self, db_session, schedule_run):
        """Test listing schedule runs."""
        runs = list_schedule_runs(db_session)
        
        assert len(runs) >= 1
        run_ids = [r.id for r in runs]
        assert schedule_run.id in run_ids

    def test_delete_schedule_run(self, db_session):
        """Test deleting a schedule run."""
        # Create a run specifically for deletion
        run = create_schedule_run(
            db=db_session,
            target_year=2097,
            target_month=12,
            currency="USD",
            include_inactive=False,
            summary={},
            export_path="exports/to_delete.csv",
        )
        run_id = run.id
        
        delete_schedule_run(db_session, run)
        
        # Verify it's deleted
        result = get_schedule_run(db_session, run_id)
        assert result is None


class TestPayoutCrud:
    """Tests for Payout CRUD operations."""

    def test_get_payout(self, db_session, test_model, schedule_run):
        """Test getting a payout by ID."""
        # Create a payout directly
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=date(2099, 1, 15),
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("1000.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        result = get_payout(db_session, payout.id)
        
        assert result is not None
        assert result.id == payout.id
        assert result.amount == Decimal("1000.00")

    def test_get_payout_not_found(self, db_session):
        """Test getting a non-existent payout."""
        result = get_payout(db_session, 999999)
        assert result is None

    def test_list_payouts_for_run(self, db_session, test_model, schedule_run):
        """Test listing payouts for a schedule run."""
        # Create some payouts
        for i in range(3):
            payout = Payout(
                schedule_run_id=schedule_run.id,
                model_id=test_model.id,
                pay_date=date(2099, 1, 15 + i),
                code=test_model.code,
                real_name=test_model.real_name,
                working_name=test_model.working_name,
                payment_method="bank",
                payment_frequency="monthly",
                amount=Decimal("100.00"),
                status="not_paid",
            )
            db_session.add(payout)
        db_session.flush()
        
        payouts = list_payouts_for_run(db_session, schedule_run.id)
        
        assert len(payouts) >= 3

    def test_list_payouts_for_model(self, db_session, test_model, schedule_run):
        """Test listing payouts for a model."""
        # Create a payout
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=date(2099, 1, 20),
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("500.00"),
            status="paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        payouts = list_payouts_for_model(db_session, test_model.id)
        
        assert len(payouts) >= 1

    def test_total_paid_by_model(self, db_session, test_model, schedule_run):
        """Test calculating total paid by model."""
        # Create paid payouts
        for amount in [Decimal("100.00"), Decimal("200.00")]:
            payout = Payout(
                schedule_run_id=schedule_run.id,
                model_id=test_model.id,
                pay_date=date(2099, 1, 21),
                code=test_model.code,
                real_name=test_model.real_name,
                working_name=test_model.working_name,
                payment_method="bank",
                payment_frequency="monthly",
                amount=amount,
                status="paid",
            )
            db_session.add(payout)
        db_session.flush()
        
        totals = total_paid_by_model(db_session, [test_model.id])
        
        assert test_model.id in totals
        # Total should include the payouts we created
        assert totals[test_model.id] >= Decimal("300.00")

    def test_total_paid_by_model_empty_list(self, db_session):
        """Test total_paid_by_model with empty list."""
        result = total_paid_by_model(db_session, [])
        assert result == {}


class TestPayoutAggregations:
    """Tests for payout aggregation functions."""

    def test_payout_status_counts(self, db_session, test_model, schedule_run):
        """Test counting payouts by status."""
        # Create payouts with different statuses
        for status in ["paid", "paid", "not_paid"]:
            payout = Payout(
                schedule_run_id=schedule_run.id,
                model_id=test_model.id,
                pay_date=date(2099, 1, 22),
                code=test_model.code,
                real_name=test_model.real_name,
                working_name=test_model.working_name,
                payment_method="bank",
                payment_frequency="monthly",
                amount=Decimal("100.00"),
                status=status,
            )
            db_session.add(payout)
        db_session.flush()
        
        counts = payout_status_counts(db_session, schedule_run.id)
        
        assert "paid" in counts
        assert counts["paid"] >= 2

    def test_payment_methods_for_run(self, db_session, test_model, schedule_run):
        """Test getting distinct payment methods for a run."""
        # Create a payout
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=date(2099, 1, 23),
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("100.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        methods = payment_methods_for_run(db_session, schedule_run.id)
        
        assert "bank" in methods

    def test_frequencies_for_run(self, db_session, test_model, schedule_run):
        """Test getting distinct frequencies for a run."""
        # Create a payout
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=date(2099, 1, 24),
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("100.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        freqs = frequencies_for_run(db_session, schedule_run.id)
        
        assert "monthly" in freqs

    def test_payout_codes_for_run(self, db_session, test_model, schedule_run):
        """Test getting distinct codes for a run."""
        # Create a payout
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=date(2099, 1, 25),
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("100.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        codes = payout_codes_for_run(db_session, schedule_run.id)
        
        assert test_model.code in codes

    def test_payout_dates_for_run(self, db_session, test_model, schedule_run):
        """Test getting distinct pay dates for a run."""
        pay_date = date(2099, 1, 26)
        payout = Payout(
            schedule_run_id=schedule_run.id,
            model_id=test_model.id,
            pay_date=pay_date,
            code=test_model.code,
            real_name=test_model.real_name,
            working_name=test_model.working_name,
            payment_method="bank",
            payment_frequency="monthly",
            amount=Decimal("100.00"),
            status="not_paid",
        )
        db_session.add(payout)
        db_session.flush()
        
        dates = payout_dates_for_run(db_session, schedule_run.id)
        
        assert pay_date in dates

    def test_run_payment_summary(self, db_session, test_model, schedule_run):
        """Test getting payment summary for a run."""
        # Create paid and unpaid payouts
        for status, amount in [("paid", Decimal("100.00")), ("not_paid", Decimal("200.00"))]:
            payout = Payout(
                schedule_run_id=schedule_run.id,
                model_id=test_model.id,
                pay_date=date(2099, 1, 27),
                code=test_model.code,
                real_name=test_model.real_name,
                working_name=test_model.working_name,
                payment_method="bank",
                payment_frequency="monthly",
                amount=amount,
                status=status,
            )
            db_session.add(payout)
        db_session.flush()
        
        summary = run_payment_summary(db_session, schedule_run.id)
        
        assert "paid_total" in summary
        assert "unpaid_total" in summary
        assert "total_payout" in summary
