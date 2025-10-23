from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import crud
from app.schemas import ModelCreate, AdhocPaymentCreate
from app.models import Payout, ScheduleRun, ValidationIssue, ModelCompensationAdjustment, AdhocPayment


def _create_model(db: Session) -> int:
    payload = ModelCreate(
        status="Active",
        code="PURGE01",
        real_name="Purge Target",
        working_name="Purge Target",
        start_date=date(2024, 1, 1),
        payment_method="Bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
        crypto_wallet=None,
    )
    model = crud.create_model(db, payload)
    return model.id


def _seed_related(db: Session, model_id: int) -> int:
    # Create a run
    run = crud.create_schedule_run(
        db,
        target_year=2024,
        target_month=9,
        currency="USD",
        include_inactive=False,
        summary={"models_paid": 0, "total_payout": Decimal("0"), "frequency_counts": {}},
        export_path="exports",
    )
    # Add payouts
    db.add_all(
        [
            Payout(
                schedule_run_id=run.id,
                model_id=model_id,
                pay_date=date(2024, 9, 15),
                code="PURGE01",
                real_name="Purge Target",
                working_name="Purge Target",
                payment_method="Bank",
                payment_frequency="monthly",
                amount=Decimal("100.00"),
                notes=None,
                status="paid",
            ),
            Payout(
                schedule_run_id=run.id,
                model_id=model_id,
                pay_date=date(2024, 9, 30),
                code="PURGE01",
                real_name="Purge Target",
                working_name="Purge Target",
                payment_method="Bank",
                payment_frequency="monthly",
                amount=Decimal("200.00"),
                notes=None,
                status="not_paid",
            ),
        ]
    )
    # Add a validation issue
    db.add(
        ValidationIssue(
            schedule_run_id=run.id,
            model_id=model_id,
            severity="warning",
            issue="Test issue",
        )
    )
    # Add an adjustment
    db.add(
        ModelCompensationAdjustment(
            model_id=model_id,
            effective_date=date(2024, 2, 1),
            amount_monthly=Decimal("1200.00"),
            notes="raise",
            created_at=date(2024, 2, 1),
            created_by="test",
        )
    )
    # Add an adhoc payment
    db.add(
        AdhocPayment(
            model_id=model_id,
            pay_date=date(2024, 3, 1),
            amount=Decimal("50.00"),
            description="bonus",
            notes=None,
            status="pending",
        )
    )
    db.commit()
    return run.id


def test_purge_model_flow(test_db: Session):
    model_id = _create_model(test_db)
    run_id = _seed_related(test_db, model_id)

    # Preview impact
    impact = crud.get_model_purge_impact(test_db, model_id)
    assert impact["payouts_total"] == 2
    assert impact["payouts_paid"] == 1
    assert impact["payouts_unpaid"] == 1
    assert impact["payouts_paid_amount"] == Decimal("100.00")
    assert impact["payouts_unpaid_amount"] == Decimal("200.00")
    assert impact["validations"] == 1
    assert impact["adhoc_payments"] == 1
    assert int(impact["adjustments"]) >= 1

    # Execute purge
    crud.purge_model_hard(test_db, model_id)

    # Verify model removed
    assert crud.get_model(test_db, model_id) is None

    # Verify related data removed
    assert test_db.query(Payout).filter(Payout.model_id == model_id).count() == 0
    assert test_db.query(ValidationIssue).filter(ValidationIssue.model_id == model_id).count() == 0
    assert test_db.query(AdhocPayment).filter(AdhocPayment.model_id == model_id).count() == 0
    assert (
        test_db.query(ModelCompensationAdjustment)
        .filter(ModelCompensationAdjustment.model_id == model_id)
        .count()
        == 0
    )

    # Run should still exist
    assert crud.get_schedule_run(test_db, run_id) is not None
