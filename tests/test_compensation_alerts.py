"""Tests for compensation alert functionality."""
from datetime import date
from decimal import Decimal

import pytest

from app import crud
from app.models import Model, Payout, ScheduleRun, PayoutCompensationAlert


@pytest.fixture
def model_with_payout(test_db):
    """Create a model with an associated schedule run and payout."""
    # Create model
    model = Model(
        status="Active",
        code="TEST001",
        real_name="Test Model",
        working_name="Testy",
        start_date=date(2025, 1, 1),
        payment_method="Bank Transfer",
        payment_frequency="monthly",
        amount_monthly=Decimal("5000.00"),
    )
    test_db.add(model)
    test_db.flush()
    
    # Create schedule run
    run = ScheduleRun(
        target_year=2026,
        target_month=1,
        currency="USD",
        include_inactive=False,
        summary_models_paid=1,
        summary_total_payout=Decimal("5000.00"),
        summary_frequency_counts="{}",
    )
    test_db.add(run)
    test_db.flush()
    
    # Create payout
    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id,
        pay_date=date(2026, 1, 31),
        code=model.code,
        real_name=model.real_name,
        working_name=model.working_name,
        payment_method=model.payment_method,
        payment_frequency=model.payment_frequency,
        amount=Decimal("5000.00"),
        status="not_paid",
    )
    test_db.add(payout)
    test_db.commit()
    
    return model, run, payout


class TestCompensationAlertCreation:
    """Tests for creating compensation alerts."""
    
    def test_create_compensation_alert(self, test_db, model_with_payout):
        """Test creating a basic compensation alert."""
        model, run, payout = model_with_payout
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
            alert_type="compensation_changed",
        )
        
        assert alert.id is not None
        assert alert.payout_id == payout.id
        assert alert.model_id == model.id
        assert alert.schedule_run_id == run.id
        assert alert.original_amount == Decimal("5000.00")
        assert alert.new_amount == Decimal("6000.00")
        assert alert.status == "pending"
        assert alert.alert_type == "compensation_changed"
    
    def test_create_alert_with_prorated_amount(self, test_db, model_with_payout):
        """Test creating an alert with a pro-rated amount."""
        model, run, payout = model_with_payout
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
            prorated_amount=Decimal("5548.39"),
        )
        
        assert alert.prorated_amount == Decimal("5548.39")
    
    def test_update_existing_alert(self, test_db, model_with_payout):
        """Test that creating alert for same payout/date updates existing."""
        model, run, payout = model_with_payout
        
        # Create first alert
        alert1 = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        first_id = alert1.id
        
        # Create second alert for same payout/date
        alert2 = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("7000.00"),  # Different amount
            effective_date=date(2026, 1, 15),
        )
        
        # Should be the same alert, just updated
        assert alert2.id == first_id
        assert alert2.new_amount == Decimal("7000.00")


class TestAlertListing:
    """Tests for listing and querying alerts."""
    
    def test_list_alerts_for_run(self, test_db, model_with_payout):
        """Test listing alerts filtered by schedule run."""
        model, run, payout = model_with_payout
        
        # Create alert
        crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        alerts = crud.list_compensation_alerts(test_db, schedule_run_id=run.id)
        assert len(alerts) == 1
        assert alerts[0].payout_id == payout.id
    
    def test_count_pending_alerts(self, test_db, model_with_payout):
        """Test counting pending alerts for a run."""
        model, run, payout = model_with_payout
        
        # Initially no alerts
        assert crud.count_pending_alerts_for_run(test_db, run.id) == 0
        
        # Create alert
        crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        # Now should have 1 pending alert
        assert crud.count_pending_alerts_for_run(test_db, run.id) == 1
    
    def test_get_alert_for_payout(self, test_db, model_with_payout):
        """Test getting a pending alert for a specific payout."""
        model, run, payout = model_with_payout
        
        # Create alert
        crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        alert = crud.get_alert_for_payout(test_db, payout.id)
        assert alert is not None
        assert alert.payout_id == payout.id


class TestAlertResolution:
    """Tests for resolving compensation alerts."""
    
    def test_resolve_alert_as_applied(self, test_db, model_with_payout):
        """Test resolving an alert by applying changes."""
        model, run, payout = model_with_payout
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        # Resolve as applied
        resolved = crud.resolve_compensation_alert(
            db=test_db,
            alert=alert,
            status="applied",
            resolved_by="test_admin",
        )
        test_db.commit()
        
        assert resolved.status == "applied"
        assert resolved.resolved_by == "test_admin"
        assert resolved.resolved_at is not None
    
    def test_resolve_alert_as_dismissed(self, test_db, model_with_payout):
        """Test dismissing an alert without applying changes."""
        model, run, payout = model_with_payout
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        resolved = crud.resolve_compensation_alert(
            db=test_db,
            alert=alert,
            status="dismissed",
        )
        test_db.commit()
        
        assert resolved.status == "dismissed"
    
    def test_apply_alert_to_payout(self, test_db, model_with_payout):
        """Test applying an alert which updates the payout amount."""
        model, run, payout = model_with_payout
        original_payout_amount = payout.amount
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        # Apply the alert
        updated_payout, resolved_alert = crud.apply_alert_to_payout(
            db=test_db,
            alert=alert,
            amount_to_apply=Decimal("6000.00"),
            resolved_by="test_admin",
        )
        test_db.commit()
        
        assert updated_payout.amount == Decimal("6000.00")
        assert resolved_alert.status == "applied"
    
    def test_invalid_resolution_status(self, test_db, model_with_payout):
        """Test that invalid resolution status raises error."""
        model, run, payout = model_with_payout
        
        alert = crud.create_compensation_alert(
            db=test_db,
            payout=payout,
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        test_db.commit()
        
        with pytest.raises(ValueError):
            crud.resolve_compensation_alert(
                db=test_db,
                alert=alert,
                status="invalid_status",
            )


class TestProRataCalculation:
    """Tests for pro-rata compensation calculation."""
    
    def test_prorata_monthly_mid_month_change(self):
        """Test pro-rata calculation for monthly payment with mid-month change."""
        # Model gets a raise on Jan 15
        # Original: $5000/month, New: $6000/month
        # January has 31 days
        # Days at old rate: 14 (Jan 1-14)
        # Days at new rate: 17 (Jan 15-31)
        
        prorated = crud.calculate_prorated_compensation(
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
            pay_date=date(2026, 1, 31),
            target_year=2026,
            target_month=1,
            payment_frequency="monthly",
        )
        
        # Expected: (5000/31 * 14) + (6000/31 * 17) = 2258.06 + 3290.32 = ~5548.39
        assert prorated > Decimal("5500.00")
        assert prorated < Decimal("5600.00")
    
    def test_prorata_weekly_after_effective(self):
        """Test that weekly payment uses new rate if pay date is after effective."""
        prorated = crud.calculate_prorated_compensation(
            original_amount=Decimal("5000.00"),
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
            pay_date=date(2026, 1, 21),  # After effective date
            target_year=2026,
            target_month=1,
            payment_frequency="weekly",
        )
        
        # Weekly = monthly / 4, so $6000 / 4 = $1500
        assert prorated == Decimal("1500.00")
    
    def test_prorata_weekly_before_effective(self):
        """Test that weekly payment keeps original if pay date is before effective."""
        prorated = crud.calculate_prorated_compensation(
            original_amount=Decimal("1250.00"),  # This would be the weekly amount
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 20),
            pay_date=date(2026, 1, 14),  # Before effective date
            target_year=2026,
            target_month=1,
            payment_frequency="weekly",
        )
        
        # Should keep original amount since pay date is before effective
        assert prorated == Decimal("1250.00")


class TestAlertGeneration:
    """Tests for automatic alert generation on compensation change."""
    
    def test_generate_alerts_for_compensation_change(self, test_db, model_with_payout):
        """Test that alerts are generated when compensation changes."""
        model, run, payout = model_with_payout
        
        # Change model's compensation
        new_amount = Decimal("6000.00")
        effective_date = date(2026, 1, 15)
        
        alerts = crud.generate_alerts_for_compensation_change(
            db=test_db,
            model=model,
            new_amount=new_amount,
            effective_date=effective_date,
        )
        test_db.commit()
        
        assert len(alerts) == 1
        assert alerts[0].payout_id == payout.id
        assert alerts[0].new_amount == new_amount
    
    def test_no_alerts_for_paid_payouts(self, test_db, model_with_payout):
        """Test that alerts are not generated for already-paid payouts."""
        model, run, payout = model_with_payout
        
        # Mark payout as paid
        payout.status = "paid"
        test_db.commit()
        
        # Try to generate alerts
        alerts = crud.generate_alerts_for_compensation_change(
            db=test_db,
            model=model,
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),
        )
        
        # Should not create alert for paid payout
        assert len(alerts) == 0
    
    def test_no_alerts_for_past_pay_dates(self, test_db, model_with_payout):
        """Test that alerts respect pay dates relative to effective date."""
        model, run, payout = model_with_payout
        
        # Set payout pay_date to before the effective date
        payout.pay_date = date(2026, 1, 10)
        test_db.commit()
        
        # Try to generate alerts with effective date after the payout
        alerts = crud.generate_alerts_for_compensation_change(
            db=test_db,
            model=model,
            new_amount=Decimal("6000.00"),
            effective_date=date(2026, 1, 15),  # After the pay date
        )
        
        # Should not create alert because pay_date is before effective_date
        assert len(alerts) == 0
