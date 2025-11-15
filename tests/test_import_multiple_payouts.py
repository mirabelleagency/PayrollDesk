from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd

from app.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.importers.excel_importer import ImportOptions, RunOptions, import_from_excel
from app.models import Model, Payout


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_import_multiple_payout_rows_creates_all():
    session = _make_session()
    try:
        # Seed two models with possible stray spaces to verify normalization
        session.add_all([
            Model(code=" A ", status="Active", real_name="A R", working_name="A W", start_date=date(2025,1,1), payment_method="Crypto", payment_frequency="monthly", amount_monthly=Decimal("100")),
            Model(code="B", status="Active", real_name="B R", working_name="B W", start_date=date(2025,1,1), payment_method="Crypto", payment_frequency="monthly", amount_monthly=Decimal("100")),
        ])
        session.commit()

        models_df = pd.DataFrame([
            {"Code": "A", "Status": "Active", "Real Name": "A R", "Working Name": "A W", "Start Date": "2025-01-01", "Payment Method": "Crypto", "Payment Frequency": "Monthly", "Monthly Amount": 100},
            {"Code": "B", "Status": "Active", "Real Name": "B R", "Working Name": "B W", "Start Date": "2025-01-01", "Payment Method": "Crypto", "Payment Frequency": "Monthly", "Monthly Amount": 100},
        ])
        payouts_df = pd.DataFrame([
            {"Code": "A", "Pay Date": "2025/10/31", "Amount": 100, "Status": "Paid", "Payment Method": "Crypto"},
            {"Code": "B", "Pay Date": "2025/10/31", "Amount": 200, "Status": "Paid", "Payment Method": "Crypto"},
        ])

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            models_df.to_excel(writer, sheet_name="Models", index=False)
            payouts_df.to_excel(writer, sheet_name="Payouts", index=False)
        workbook_bytes = buffer.getvalue()

        import_options = ImportOptions(update_existing=True)
        run_options = RunOptions(create_schedule_run=True, target_year=2025, target_month=10, currency="USD", export_dir="exports")
        summary = import_from_excel(session, workbook_bytes, import_options, run_options)

        assert summary.payout_errors == []
        payouts = session.query(Payout).all()
        assert len(payouts) == 2
        amounts = sorted([p.amount for p in payouts])
        assert amounts == [Decimal("100"), Decimal("200")]
    finally:
        session.close()
