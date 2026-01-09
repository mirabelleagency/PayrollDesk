"""Application service layer."""
from __future__ import annotations

import calendar
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.core.payroll import (
    ModelRecord,
    build_models_table,
    build_pay_schedule,
    build_validation_report,
    ensure_non_empty_frames,
    export_outputs,
    validate_row,
)
from app import crud
from app.models import Model


class PayrollService:
    """Coordinates payroll operations using database state."""

    def __init__(self, db: Session) -> None:
        self.db = db

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
        # Check if a payroll run already exists for this month/year
        existing_runs = crud.list_schedule_runs(
            self.db, target_year=target_year, target_month=target_month
        )
        
        # Preserve old payout status and notes for matching payouts
        old_payout_data = {}
        if existing_runs:
            run = existing_runs[0]  # Use the most recent run for this month
            # Save status and notes from old payouts before clearing
            for payout in run.payouts:
                key = (payout.code, payout.pay_date)
                old_payout_data[key] = {
                    "status": payout.status,
                    "notes": payout.notes,
                }
            # Clear old payouts and validations so we can refresh with current data
            crud.clear_schedule_data(self.db, run)
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
        records = [
            self._to_record(index, model, target_year, target_month)
            for index, model in enumerate(models, start=1)
        ]

        schedule_df, summary = build_pay_schedule(records, target_year, target_month, currency)
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
                    f"Amount Gross ({currency})": float(amount_gross),
                    f"Advances Deducted ({currency})": float(Decimal(str(allocated or 0))),
                    f"Amount Net ({currency})": float(amount_net),
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
            self._to_record(index, model, run.target_year, run.target_month)
            for index, model in enumerate(new_models, start=1)
        ]
        
        # Generate schedule only for new models
        schedule_df, _ = build_pay_schedule(records, run.target_year, run.target_month, currency)
        
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
        return {
            "added_count": len(new_models),
            "added_codes": added_codes,
            "message": f"Added {len(new_models)} new model(s) to schedule",
        }

    def _to_record(self, position: int, model: Model, target_year: int, target_month: int) -> ModelRecord:
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
        for message in validate_row(record):
            record.add_message(message.level, message.text)
        return record
