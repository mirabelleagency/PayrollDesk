"""Seed demo payroll data for local API integration testing."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "payroll_v4.db"


def _env_db_url(db_path: Path) -> None:
    os.environ.setdefault("PAYROLL_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("API_RATE_SECRET", "dev-rate-secret-for-local-testing-32c")
    os.environ.setdefault("API_CURSOR_SECRET", "dev-cursor-secret-for-local-test-32c")


def seed(session, *, force: bool = False) -> dict[str, int | str]:
    from app.models import (
        AdhocPayment,
        AdvanceRepayment,
        Model,
        ModelAdvance,
        ModelCompensationAdjustment,
        PayConfig,
        Payout,
        PayoutAdvanceAllocation,
        ScheduleRun,
        SyncState,
        ValidationIssue,
    )

    existing = session.query(Model).filter(Model.code == "DEMO-001").first()
    if existing and not force:
        sync = session.get(SyncState, 1)
        return {
            "skipped": 1,
            "revision": sync.revision if sync else 0,
            "message": "Demo data already present (use --force to re-seed)",
        }

    if force:
        from app import crud

        crud.reset_application_data(session)

    pay_config = session.query(PayConfig).filter(PayConfig.is_default.is_(True)).first()

    models = []
    specs = [
        ("DEMO-001", "Alex Rivera", "Alex R", "monthly", Decimal("5000.00"), "0xDEMO001WALLET", "ACH"),
        ("DEMO-002", "Blake Chen", "Blake C", "biweekly", Decimal("3200.00"), None, "Wire"),
        ("DEMO-003", "Casey Morgan", "Casey M", "weekly", Decimal("1800.00"), "0xDEMO003WALLET", "Crypto"),
    ]
    for code, real_name, working_name, freq, amount, wallet, method in specs:
        model = Model(
            status="Active",
            code=code,
            real_name=real_name,
            working_name=working_name,
            start_date=date(2025, 1, 1),
            payment_method=method,
            payment_frequency=freq,
            amount_monthly=amount,
            crypto_wallet=wallet,
        )
        session.add(model)
        models.append(model)
    session.flush()

    run = ScheduleRun(
        target_year=2026,
        target_month=9,
        currency="USD",
        include_inactive=False,
        summary_models_paid=3,
        summary_total_payout=Decimal("8750.00"),
        summary_frequency_counts=json.dumps({"monthly": 1, "biweekly": 1, "weekly": 1}),
        export_path="exports/demo_sep_2026",
        run_status="ready",
        pay_config_id=pay_config.id if pay_config else None,
    )
    session.add(run)
    session.flush()

    payout_specs = [
        (models[0], date(2026, 9, 15), Decimal("4250.00"), Decimal("5000.00"), "paid", True, "September monthly payout"),
        (models[1], date(2026, 9, 14), Decimal("1400.00"), Decimal("1600.00"), "approved", False, "Mid-month biweekly"),
        (models[1], date(2026, 9, 28), Decimal("1400.00"), None, "not_paid", False, "End-month biweekly"),
        (models[2], date(2026, 9, 7), Decimal("450.00"), Decimal("450.00"), "paid", True, "Weekly slot 1"),
        (models[2], date(2026, 9, 14), Decimal("450.00"), Decimal("450.00"), "paid", True, "Weekly slot 2"),
        (models[2], date(2026, 9, 21), Decimal("450.00"), Decimal("450.00"), "not_paid", False, "Weekly slot 3"),
    ]
    payouts: list[Payout] = []
    for model, pay_date, amount, gross, status, locked, notes in payout_specs:
        payout = Payout(
            schedule_run_id=run.id,
            model_id=model.id,
            pay_date=pay_date,
            code=model.code,
            real_name=model.real_name,
            working_name=model.working_name,
            payment_method=model.payment_method,
            payment_frequency=model.payment_frequency,
            amount=amount,
            gross_amount=gross,
            status=status,
            is_locked=locked,
            notes=notes,
        )
        session.add(payout)
        payouts.append(payout)
    session.flush()

    session.add(
        ValidationIssue(
            schedule_run_id=run.id,
            model_id=models[2].id,
            severity="warning",
            issue="Demo: missing tax form on file",
        )
    )
    session.add(
        AdhocPayment(
            model_id=models[0].id,
            pay_date=date(2026, 9, 20),
            amount=Decimal("250.00"),
            description="Demo bonus",
            notes="One-off performance bonus",
            status="paid",
        )
    )
    session.add(
        ModelCompensationAdjustment(
            model_id=models[0].id,
            effective_date=date(2026, 9, 1),
            amount_monthly=Decimal("5000.00"),
            notes="September rate",
            created_by="admin",
        )
    )

    advance = ModelAdvance(
        model_id=models[0].id,
        amount_total=Decimal("2000.00"),
        amount_remaining=Decimal("1500.00"),
        status="active",
        strategy="fixed",
        fixed_amount=Decimal("250.00"),
        notes="Demo advance",
    )
    session.add(advance)
    session.flush()

    session.add(
        AdvanceRepayment(
            advance_id=advance.id,
            payout_id=payouts[0].id,
            amount=Decimal("500.00"),
            source="auto",
        )
    )
    session.add(
        PayoutAdvanceAllocation(
            schedule_run_id=run.id,
            payout_id=payouts[0].id,
            model_id=models[0].id,
            advance_id=advance.id,
            planned_amount=Decimal("250.00"),
        )
    )

    session.commit()
    sync = session.get(SyncState, 1)
    return {
        "models": len(models),
        "schedule_run_id": run.id,
        "payouts": len(payouts),
        "revision": sync.revision,
        "period": "2026-09",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for API testing")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument("--force", action="store_true", help="Clear domain data and re-seed")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        print("Run: python scripts/recreate_local_db.py", file=sys.stderr)
        return 1

    _env_db_url(args.db)
    sys.path.insert(0, str(ROOT))

    from app.database import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        result = seed(session, force=args.force)
    finally:
        session.close()

    print("Demo seed complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()
    print("Try:")
    print('  curl -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8002/api/v2/snapshot')
    print('  curl -H "X-API-Key: YOUR_KEY" "http://127.0.0.1:8002/api/v2/schedule-runs?year=2026&month=9&snapshot_revision=REVISION"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
