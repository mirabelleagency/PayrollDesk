from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.excel_importer import ImportOptions, RunOptions, import_from_excel
from app.models import Model, Payout, ScheduleRun


def _build_workbook() -> bytes:
    models_df = pd.DataFrame(
        [
            {
                "Code": "ALPHA1",
                "Status": "Active",
                "Real Name": "Alex Smith",
                "Working Name": "Alpha",
                "Start Date": "2024-01-01",
                "Payment Method": "Wire",
                "Payment Frequency": "Monthly",
                "Monthly Amount": 5000,
                "Crypto Wallet": "",
            }
        ]
    )
    payouts_df = pd.DataFrame(
        [
            {
                "Code": "ALPHA1",
                "Pay Date": "2024-02-01",
                "Amount": 2500,
                "Status": "Paid",
            }
        ]
    )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        models_df.to_excel(writer, sheet_name="Models", index=False)
        payouts_df.to_excel(writer, sheet_name="Payouts", index=False)
    return buffer.getvalue()


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_import_payouts_without_name_columns():
    session = _make_session()
    try:
        workbook_bytes = _build_workbook()
        import_options = ImportOptions()
        run_options = RunOptions(
            create_schedule_run=True,
            target_year=2024,
            target_month=2,
            currency="USD",
            export_dir="exports",
            auto_generate_runs=False,
        )

        summary = import_from_excel(session, workbook_bytes, import_options, run_options)

        assert summary.model_errors == []
        assert summary.payout_errors == []
        assert summary.payouts_created == 1
        assert summary.schedule_run_id is not None

        model = session.query(Model).filter_by(code="ALPHA1").one()
        payout = session.query(Payout).one()
        run = session.query(ScheduleRun).one()

        assert payout.model_id == model.id
        assert payout.schedule_run_id == run.id
        assert payout.real_name == model.real_name
        assert payout.working_name == model.working_name
        assert payout.payment_method == model.payment_method
        assert payout.payment_frequency == model.payment_frequency
    finally:
        session.close()


def test_import_payouts_updates_existing_without_overwriting_others():
    session = _make_session()
    try:
        # Pre-existing models and payouts in the target run
        model_a = Model(
            code="ALPHA1",
            status="Active",
            real_name="Alex Smith",
            working_name="Alpha",
            start_date=date(2024, 1, 1),
            payment_method="Wire",
            payment_frequency="Monthly",
            amount_monthly=Decimal("5000"),
        )
        model_b = Model(
            code="BETA2",
            status="Active",
            real_name="Bri Jones",
            working_name="Beta",
            start_date=date(2024, 1, 1),
            payment_method="Wire",
            payment_frequency="Monthly",
            amount_monthly=Decimal("4500"),
        )
        session.add_all([model_a, model_b])
        session.flush()

        run = ScheduleRun(
            target_year=2024,
            target_month=2,
            currency="USD",
            include_inactive=False,
            summary_models_paid=0,
            summary_total_payout=Decimal("0"),
            summary_frequency_counts="{}",
            export_path="exports",
        )
        session.add(run)
        session.flush()

        original_alpha_payout = Payout(
            schedule_run_id=run.id,
            model_id=model_a.id,
            pay_date=date(2024, 2, 1),
            code="ALPHA1",
            real_name=model_a.real_name,
            working_name=model_a.working_name,
            payment_method=model_a.payment_method,
            payment_frequency=model_a.payment_frequency,
            amount=Decimal("2500"),
            status="paid",
            notes="original",
        )
        beta_payout = Payout(
            schedule_run_id=run.id,
            model_id=model_b.id,
            pay_date=date(2024, 2, 3),
            code="BETA2",
            real_name=model_b.real_name,
            working_name=model_b.working_name,
            payment_method=model_b.payment_method,
            payment_frequency=model_b.payment_frequency,
            amount=Decimal("2200"),
            status="paid",
            notes="keep",
        )
        session.add_all([original_alpha_payout, beta_payout])
        session.flush()

        # Workbook with updated payout info only for ALPHA1
        models_df = pd.DataFrame(
            [
                {
                    "Code": "ALPHA1",
                    "Status": "Active",
                    "Real Name": "Alex Smith",
                    "Working Name": "Alpha",
                    "Start Date": "2024-01-01",
                    "Payment Method": "Wire",
                    "Payment Frequency": "Monthly",
                    "Monthly Amount": 5000,
                    "Crypto Wallet": "",
                }
            ]
        )
        payouts_df = pd.DataFrame(
            [
                {
                    "Code": "ALPHA1",
                    "Pay Date": "2024-02-01",
                    "Amount": 3000,
                    "Status": "Not Paid",
                    "Notes": "updated",
                }
            ]
        )

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            models_df.to_excel(writer, sheet_name="Models", index=False)
            payouts_df.to_excel(writer, sheet_name="Payouts", index=False)
        workbook_bytes = buffer.getvalue()

        import_options = ImportOptions(update_existing=True)
        run_options = RunOptions(
            schedule_run_id=run.id,
            create_schedule_run=False,
            target_year=2024,
            target_month=2,
            currency="USD",
            export_dir="exports",
        )

        summary = import_from_excel(session, workbook_bytes, import_options, run_options)

        payouts = session.query(Payout).filter(Payout.schedule_run_id == run.id).all()
        assert len(payouts) == 2

        updated_alpha = next(p for p in payouts if p.code == "ALPHA1")
        untouched_beta = next(p for p in payouts if p.code == "BETA2")

        assert updated_alpha.amount == Decimal("3000")
        assert updated_alpha.status == "not_paid"
        assert updated_alpha.notes == "updated"
        assert untouched_beta.amount == Decimal("2200")
        assert untouched_beta.status == "paid"
        assert untouched_beta.notes == "keep"

        # Only new payouts should be counted as created
        assert summary.payouts_created == 0
        assert summary.payout_errors == []
    finally:
        session.close()
