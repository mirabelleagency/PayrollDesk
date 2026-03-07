"""Application service layer."""
from __future__ import annotations

import calendar
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.core.payroll import (
    ModelRecord,
    build_models_table,
    build_pay_schedule,
    build_validation_report,
    ensure_non_empty_frames,
    export_outputs,
    get_pay_dates,
    validate_row,
)
from app import crud
from app.models import Model, PayConfig, FrequencyPlan


class PayrollService:
    """Coordinates payroll operations using database state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_pay_days(self) -> Optional[List]:
        """Load pay days from default PayConfig, or None for defaults."""
        config = self.db.query(PayConfig).filter(PayConfig.is_default == True).first()
        if config:
            return json.loads(config.pay_days)
        return None

    def _load_frequency_plans(self) -> Optional[Dict[str, List[int]]]:
        """Load frequency plans from DB, or None for defaults."""
        plans = self.db.query(FrequencyPlan).filter(FrequencyPlan.is_active == True).all()
        if plans:
            return {p.name: json.loads(p.pay_day_indices) for p in plans}
        return None

    def list_models(self) -> Iterable[Model]:
        return crud.list_models(self.db)

    def create_model(self, payload) -> Model:
        return crud.create_model(self.db, payload)

    def update_model(self, model: Model, payload) -> Model:
        return crud.update_model(self.db, model, payload)

    def delete_model(self, model: Model) -> None:
        crud.delete_model(self.db, model)

    def run_payroll(
        self,
        target_year: int,
        target_month: int,
        currency: str,
        include_inactive: bool,
        output_dir: Path,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, int]:
        # Load config from DB
        pay_days = self._load_pay_days()
        freq_plans = self._load_frequency_plans()

        try:
            return self._run_payroll_inner(
                target_year, target_month, currency, include_inactive,
                output_dir, pay_days, freq_plans,
            )
        except Exception:
            self.db.rollback()
            raise

    def _run_payroll_inner(
        self,
        target_year: int,
        target_month: int,
        currency: str,
        include_inactive: bool,
        output_dir: Path,
        pay_days: Optional[List],
        freq_plans: Optional[Dict[str, List[int]]],
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, int]:
        # Check if a payroll run already exists for this month/year
        existing_runs = crud.list_schedule_runs(
            self.db, target_year=target_year, target_month=target_month
        )
        
        # Preserve old payout status and notes for matching payouts
        old_payout_data = {}
        locked_codes: set[str] = set()
        if existing_runs:
            run = existing_runs[0]  # Use the most recent run for this month
            # Save status and notes from old payouts before clearing
            for payout in run.payouts:
                key = (payout.code, payout.pay_date)
                if payout.is_locked:
                    locked_codes.add(payout.code)
                else:
                    old_payout_data[key] = {
                        "status": payout.status,
                        "notes": payout.notes,
                    }
            # Clear only unlocked payouts (locked ones stay)
            crud.clear_unlocked_schedule_data(self.db, run)
        else:
            run = crud.create_schedule_run(
                self.db,
                target_year=target_year,
                target_month=target_month,
                currency=currency,
                include_inactive=include_inactive,
                summary={},  # Will be updated below
                export_path=str(output_dir),
            )
        
        models = crud.list_models(self.db)
        # Only recalculate for non-locked models
        models_to_calc = [m for m in models if m.code not in locked_codes]
        records = [
            self._to_record(index, model, target_year, target_month, freq_plans)
            for index, model in enumerate(models_to_calc, start=1)
        ]

        schedule_df, summary = build_pay_schedule(
            records, target_year, target_month, currency,
            pay_days=pay_days, frequency_plans=freq_plans,
        )
        models_df = build_models_table(records, currency)
        validation_df = build_validation_report(records, include_inactive)

        schedule_df, models_df, validation_df = ensure_non_empty_frames(
            schedule_df, models_df, validation_df, currency
        )

        # Update the run with new summary data
        run.summary_models_paid = summary.get("models_paid", 0)
        run.summary_total_payout = Decimal(str(summary.get("total_payout", 0)))
        run.summary_frequency_counts = json.dumps(summary.get("frequency_counts", {}))
        self.db.commit()

        amount_column = f"Amount ({currency})"
        payout_records = schedule_df.to_dict(orient="records")
        for payout in payout_records:
            pay_date_value = payout.get("Pay Date")
            if pay_date_value is not None and hasattr(pay_date_value, "date"):
                payout["Pay Date"] = pay_date_value.date()
            amount_value = payout.get(amount_column)
            if amount_value is not None:
                payout[amount_column] = Decimal(str(amount_value))
            notes_value = payout.get("Notes")
            if notes_value is None or (isinstance(notes_value, float) and pd.isna(notes_value)):
                payout["Notes"] = None

        crud.store_payouts(
            self.db,
            run,
            payout_records,
            amount_column=amount_column,
            old_payout_data=old_payout_data,
        )
        crud.store_validation_messages(self.db, run, records, include_inactive)

        # Log amendment
        affected_codes = [r.code for r in records]
        amendment_type = "refresh" if existing_runs else "initial"
        crud.create_amendment(
            self.db, run, amendment_type, affected_codes,
            [{"action": amendment_type, "models_count": len(affected_codes),
              "locked_count": len(locked_codes)}],
        )

        # Build export schedule from DB payouts to reflect cash advance deductions (net vs gross)
        payouts_with_allocs = crud.list_payouts_with_allocations_for_run(self.db, run.id)
        # Assemble DataFrame with Gross, Advances Deducted, Net columns
        export_rows: list[dict] = []
        for payout, allocated in payouts_with_allocs:
            amount_net = Decimal(str(payout.amount or 0))
            amount_gross = amount_net + Decimal(str(allocated or 0))
            export_rows.append(
                {
                    "Pay Date": payout.pay_date,
                    "Code": payout.code,
                    "Real Name": payout.real_name,
                    "Working Name": payout.working_name,
                    "Payment Method": payout.payment_method,
                    "Payment Frequency": payout.payment_frequency.title() if payout.payment_frequency else "",
                    f"Amount Gross ({currency})": str(amount_gross),
                    f"Advances Deducted ({currency})": str(Decimal(str(allocated or 0))),
                    f"Amount Net ({currency})": str(amount_net),
                    "Status": payout.status.replace("_", " ").title() if payout.status else "",
                    "Notes": payout.notes or "",
                }
            )

        export_schedule_df = pd.DataFrame(export_rows)
        if not export_schedule_df.empty:
            export_schedule_df = export_schedule_df.sort_values(["Pay Date", "Code"]).reset_index(drop=True)
            export_schedule_df["Pay Date"] = pd.to_datetime(export_schedule_df["Pay Date"])  # type: ignore[index]

        export_outputs(
            base_filename=f"pay_schedule_{target_year:04d}_{target_month:02d}_run{run.id}",
            schedule_df=export_schedule_df,
            models_df=models_df,
            validation_df=validation_df,
            output_dir=output_dir,
        )

        return schedule_df, models_df, validation_df, summary, run.id

    def add_new_models_to_run(
        self,
        run_id: int,
        currency: str,
    ) -> dict:
        """Add payouts for models that don't have payouts in the run yet.
        
        This is a SAFE operation - it never modifies or deletes existing payouts.
        Only models that are not yet in the schedule will be added.
        
        Returns a dict with counts of models added.
        """
        pay_days = self._load_pay_days()
        freq_plans = self._load_frequency_plans()

        run = crud.get_schedule_run(self.db, run_id)
        if not run:
            raise ValueError(f"Schedule run {run_id} not found")
        
        # Get codes already in the schedule
        existing_codes = set(crud.payout_codes_for_run(self.db, run_id))
        
        # Get all models
        all_models = crud.list_models(self.db)
        
        # Filter to only models not already in schedule
        new_models = [m for m in all_models if m.code not in existing_codes]
        
        if not new_models:
            return {"added_count": 0, "added_codes": [], "message": "No new models to add"}
        
        # Build records only for new models
        records = [
            self._to_record(index, model, run.target_year, run.target_month, freq_plans)
            for index, model in enumerate(new_models, start=1)
        ]
        
        # Generate schedule only for new models
        schedule_df, _ = build_pay_schedule(
            records, run.target_year, run.target_month, currency,
            pay_days=pay_days, frequency_plans=freq_plans,
        )
        
        if schedule_df.empty:
            return {"added_count": 0, "added_codes": [], "message": "No payouts generated for new models"}
        
        # Convert to payout records
        amount_column = f"Amount ({currency})"
        payout_records = schedule_df.to_dict(orient="records")
        for payout in payout_records:
            pay_date_value = payout.get("Pay Date")
            if pay_date_value is not None and hasattr(pay_date_value, "date"):
                payout["Pay Date"] = pay_date_value.date()
            amount_value = payout.get(amount_column)
            if amount_value is not None:
                payout[amount_column] = Decimal(str(amount_value))
            notes_value = payout.get("Notes")
            if notes_value is None or (isinstance(notes_value, float) and pd.isna(notes_value)):
                payout["Notes"] = None
        
        # Store new payouts (no old_payout_data since these are all new)
        crud.store_payouts(
            self.db,
            run,
            payout_records,
            amount_column=amount_column,
            old_payout_data={},  # No old data to preserve for new models
        )
        
        # Store validation messages for new models
        crud.store_validation_messages(self.db, run, records, include_inactive=False)
        
        added_codes = [m.code for m in new_models]

        # Log amendment
        crud.create_amendment(
            self.db, run, "add_models", added_codes,
            [{"action": "add_models", "added_count": len(added_codes)}],
        )

        return {
            "added_count": len(new_models),
            "added_codes": added_codes,
            "message": f"Added {len(new_models)} new model(s) to schedule",
        }

    def _to_record(
        self,
        position: int,
        model: Model,
        target_year: int,
        target_month: int,
        frequency_plans: Optional[Dict[str, List[int]]] = None,
    ) -> ModelRecord:
        base_amount = None
        if model.amount_monthly is not None:
            base_amount = Decimal(str(model.amount_monthly))
        adjustments = sorted(
            [
                (adjustment.effective_date, Decimal(str(adjustment.amount_monthly)))
                for adjustment in model.compensation_adjustments
            ],
            key=lambda item: item[0],
        )
        record = ModelRecord(
            row_number=position + 1,
            status=model.status,
            code=model.code,
            real_name=model.real_name,
            working_name=model.working_name,
            start_date=model.start_date,
            payment_method=model.payment_method,
            payment_frequency=model.payment_frequency.lower(),
            amount_monthly=base_amount,
            compensation_adjustments=adjustments,
        )
        for message in validate_row(record, frequency_plans):
            record.add_message(message.level, message.text)
        return record

    # ------------------------------------------------------------------
    # Auto-generation
    # ------------------------------------------------------------------

    def auto_generate_upcoming_schedules(
        self,
        months_ahead: int = 2,
        currency: str = "USD",
        output_dir: Path = Path("exports"),
    ) -> list[dict]:
        """Auto-generate draft schedule runs for upcoming months.

        Creates runs for the next *months_ahead* months that don't already
        have a schedule.  Each new run goes through the full ``run_payroll``
        pipeline so payouts, exports, and validations are all populated.

        Returns a list of dicts describing what was created.
        """
        today = date.today()
        results: list[dict] = []

        for offset in range(months_ahead):
            # Calculate target month with rollover
            month = today.month + 1 + offset
            year = today.year
            while month > 12:
                month -= 12
                year += 1

            # Skip if a run already exists for this period
            existing = crud.list_schedule_runs(
                self.db, target_year=year, target_month=month
            )
            if existing:
                results.append({
                    "year": year,
                    "month": month,
                    "status": "exists",
                    "run_id": existing[0].id,
                })
                continue

            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                _, _, _, summary, run_id = self.run_payroll(
                    target_year=year,
                    target_month=month,
                    currency=currency,
                    include_inactive=False,
                    output_dir=output_dir,
                )

                # Mark as draft
                run = crud.get_schedule_run(self.db, run_id)
                if run:
                    run.run_status = "draft"
                    self.db.commit()

                results.append({
                    "year": year,
                    "month": month,
                    "status": "created",
                    "run_id": run_id,
                    "models_paid": summary.get("models_paid", 0),
                })
            except Exception as exc:
                results.append({
                    "year": year,
                    "month": month,
                    "status": "error",
                    "error": str(exc),
                })

        return results

    def get_upcoming_pay_dates(self, months_ahead: int = 3) -> list[dict]:
        """Return upcoming pay dates across the next *months_ahead* months.

        Each entry contains the date, which models are expected to be paid,
        and status information from existing schedule runs.
        """
        today = date.today()
        pay_days = self._load_pay_days()
        freq_plans = self._load_frequency_plans() or {}

        upcoming: list[dict] = []

        for offset in range(months_ahead):
            month = today.month + offset
            year = today.year
            while month > 12:
                month -= 12
                year += 1

            dates = get_pay_dates(year, month, pay_days)

            # Check for existing run
            existing = crud.list_schedule_runs(
                self.db, target_year=year, target_month=month,
                eager_load_payouts=True,
            )
            run = existing[0] if existing else None

            for pay_date in dates:
                if pay_date < today:
                    continue

                entry: dict = {
                    "date": pay_date,
                    "year": year,
                    "month": month,
                    "month_name": calendar.month_abbr[month],
                    "has_run": run is not None,
                    "run_id": run.id if run else None,
                    "run_status": getattr(run, "run_status", None),
                }

                if run:
                    # Count payouts for this specific date
                    payouts = [
                        p for p in run.payouts if p.pay_date == pay_date
                    ]
                    paid = sum(1 for p in payouts if p.status == "paid")
                    total = len(payouts)
                    total_amount = sum(
                        Decimal(str(p.amount or 0)) for p in payouts
                    )
                    entry["payout_count"] = total
                    entry["paid_count"] = paid
                    entry["total_amount"] = total_amount
                else:
                    entry["payout_count"] = 0
                    entry["paid_count"] = 0
                    entry["total_amount"] = Decimal("0")

                upcoming.append(entry)

        upcoming.sort(key=lambda e: e["date"])
        return upcoming
