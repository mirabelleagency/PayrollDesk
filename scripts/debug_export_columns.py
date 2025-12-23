from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pandas as pd
from io import BytesIO

from app.database import Base
from app.models import Model, Payout, ScheduleRun
from app.exporting.xlsx import export_full_workbook
from decimal import Decimal
from datetime import date

# set up in-memory db
engine = create_engine(
    "sqlite:///:memory:", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
session = SessionLocal()

# seed minimal data
m = Model(code="ALPHA1", status="Active", real_name="Alex", working_name="Alpha",
          start_date=date(2024,1,1), payment_method="Wire", payment_frequency="monthly",
          amount_monthly=Decimal("5000"))
session.add(m)
session.flush()
run = ScheduleRun(target_year=2025, target_month=10, currency="USD", include_inactive=False,
                  summary_models_paid=0, summary_total_payout=Decimal("0"), summary_frequency_counts="{}",
                  export_path="exports")
session.add(run)
session.flush()

p = Payout(schedule_run_id=run.id, model_id=m.id, pay_date=date(2025,10,7), code="ALPHA1",
           real_name=m.real_name, working_name=m.working_name, payment_method=m.payment_method,
           payment_frequency=m.payment_frequency, amount=Decimal("2500"), status="not_paid", notes=None)
session.add(p)
session.commit()

# export and read back
wb_bytes = export_full_workbook(session)

# Read Payouts sheet columns
bio = BytesIO(wb_bytes)
df = pd.read_excel(bio, sheet_name="Payouts")
print(list(df.columns))
