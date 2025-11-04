from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import crud
from app.models import ScheduleRun, Payout


def test_cleanup_empty_runs_removes_runs_without_payouts(test_db: Session):
    # Create two runs: one empty, one with a payout
    run_empty = crud.create_schedule_run(
        test_db,
        target_year=2025,
        target_month=1,
        currency="USD",
        include_inactive=False,
        summary={"models_paid": 0, "total_payout": Decimal("0"), "frequency_counts": {}},
        export_path="exports",
    )
    run_with_data = crud.create_schedule_run(
        test_db,
        target_year=2025,
        target_month=2,
        currency="USD",
        include_inactive=False,
        summary={"models_paid": 0, "total_payout": Decimal("0"), "frequency_counts": {}},
        export_path="exports",
    )
    # Add a payout to the second run (no model link needed for this test)
    test_db.add(
        Payout(
            schedule_run_id=run_with_data.id,
            model_id=None,
            pay_date=date(2025, 2, 15),
            code="X",
            real_name="X",
            working_name="X",
            payment_method="Bank",
            payment_frequency="monthly",
            amount=Decimal("10.00"),
            status="not_paid",
        )
    )
    test_db.commit()

    # Cleanup
    result = crud.cleanup_empty_runs(test_db)

    # Assert empty run deleted, the other remains
    assert result["deleted_runs"] == 1
    assert crud.get_schedule_run(test_db, run_empty.id) is None
    assert crud.get_schedule_run(test_db, run_with_data.id) is not None
