import datetime
from decimal import Decimal

from app import crud
from app.models import Model, ScheduleRun, Payout, ValidationIssue, AdhocPayment, ModelCompensationAdjustment


def test_reset_application_data_clears_domain_tables_and_keeps_users(test_db):
    # Seed a model and some related data
    model = Model(
        status="Active",
        code="TST-001",
        real_name="Test Real",
        working_name="Test Worker",
        start_date=datetime.date.today(),
        payment_method="Bank",
        payment_frequency="monthly",
        amount_monthly=Decimal("1000.00"),
    )
    test_db.add(model)
    test_db.flush()

    # Adjustment and adhoc
    adj = ModelCompensationAdjustment(
        model_id=model.id,
        effective_date=model.start_date,
        amount_monthly=Decimal("1000.00"),
        notes="init",
    )
    test_db.add(adj)
    ad = AdhocPayment(
        model_id=model.id,
        pay_date=model.start_date,
        amount=Decimal("50.00"),
        description="bonus",
        status="pending",
    )
    test_db.add(ad)

    # Schedule run and payout
    run = ScheduleRun(target_year=model.start_date.year, target_month=model.start_date.month, currency="USD", include_inactive=False, summary_models_paid=0, summary_total_payout=Decimal("0"), summary_frequency_counts="{}", export_path="exports")
    test_db.add(run)
    test_db.flush()

    payout = Payout(
        schedule_run_id=run.id,
        model_id=model.id,
        pay_date=model.start_date,
        code=model.code,
        real_name=model.real_name,
        working_name=model.working_name,
        payment_method=model.payment_method,
        payment_frequency=model.payment_frequency,
        amount=Decimal("100.00"),
        status="not_paid",
    )
    test_db.add(payout)
    test_db.flush()

    issue = ValidationIssue(schedule_run_id=run.id, model_id=model.id, severity="warning", issue="test")
    test_db.add(issue)
    test_db.commit()

    # Sanity preconditions
    assert test_db.query(Model).count() == 1
    assert test_db.query(Payout).count() == 1
    assert test_db.query(ValidationIssue).count() == 1

    # Execute reset
    result = crud.reset_application_data(test_db)
    assert isinstance(result, dict)

    # All domain tables cleared
    assert test_db.query(Model).count() == 0
    assert test_db.query(Payout).count() == 0
    assert test_db.query(ValidationIssue).count() == 0
    assert test_db.query(ScheduleRun).count() == 0
    assert test_db.query(AdhocPayment).count() == 0
    assert test_db.query(ModelCompensationAdjustment).count() == 0

    # Users are kept (admin seeded by init_db)
    from app.auth import User
    assert test_db.query(User).count() >= 1
