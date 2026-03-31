# Schedules Module Status

> Audit date: 2026-03-31
> Auditor: Copilot `/audit schedules`
> Scope: `app/routers/schedules.py`, `app/services.py`,
> `app/core/payroll.py`, `app/crud.py` (schedule fns),
> `app/models.py` (schedule models), `app/templates/schedules/`

---

## Current State

### Implemented

- **Dashboard** — paginated list of schedule runs with
  month/year filters, summary cards
  (`routers/schedules.py` L1047-1489,
  `templates/schedules/list.html`)
- **Create schedule (sync + async)** — form + POST `/new`
  and `/new/async`; async uses background thread with
  progress polling
  (`routers/schedules.py` L2156-2248,
  `services.py` L57-300)
- **Run detail view** — full payout table with filters
  (status, code, frequency, payment method, pay date,
  search), pagination, inline editing, bulk actions
  (`routers/schedules.py` L2512-2650,
  `templates/schedules/detail.html`)
- **Add New Models** — adds payouts for models not yet in
  the schedule; pure INSERT, never deletes
  (`services.py` L304-365,
  `routers/schedules.py` L2665-2704)
- **Refresh schedule** — recalculates unlocked payouts,
  preserves locked payouts' status/notes
  (`routers/schedules.py` L2707-2729, `services.py`
  L126-300)
- **Lock/unlock payouts** — per-payout locking via
  `is_locked` column; locked payouts survive refresh
  (`routers/schedules.py`, `crud.py`)
- **Payout status management** — inline status updates
  (not_paid, paid, on_hold, cancelled), bulk status
  changes (`routers/schedules.py` batch endpoints,
  `crud.py` batch_update)
- **Payout notes** — inline editing via HTMX partial
  (`routers/schedules.py` update_payout_notes)
- **Export (CSV download)** — 3-file CSV export (schedule,
  models, validation) + ZIP download
  (`routers/schedules.py` L2100-2155,
  `exporting/outputs.py`)
- **Validation issues** — generated per-model during
  payroll run, stored in `validation_issues` table
  (`crud.py` store_validation_messages,
  `core/payroll.py` validate_row)
- **Amendments / audit trail** — `ScheduleAmendment` model
  tracks every schedule change (initial, refresh,
  add_models, etc.)
  (`models.py` L576, `crud.py` create_amendment)
- **Compensation alerts** — alert when a payout's amount
  differs from the model's current monthly amount
  (`models.py` L476, `crud.py` compensation alert fns)
- **Cash advance deductions** — advance allocations auto-
  applied during payroll; gross/net tracking on export
  (`crud.py` _apply_advance_allocations_for_run,
  `services.py` export_rows logic)
- **Delete schedule run** — admin-only, removes run +
  cascading payouts (`routers/schedules.py`)
- **Dashboard caching** — in-memory TTL cache (5 min,
  max 50 entries), invalidated on mutations
  (`routers/schedules.py` L37-68)
- **Combined payouts view** — cross-run payout table
  (`templates/schedules/combined_payouts.html`)
- **Adhoc payments** — separate adhoc flow linked to
  schedule runs (`templates/schedules/adhoc.html`)
- **Auto-generate upcoming schedules** —
  `auto_generate_upcoming_schedules` service method
  (`services.py` L424+)

### Partial

- **Filter preservation on redirect** — recently added for
  Add New Models flow; not yet applied to all POST
  redirects (refresh, bulk actions, etc.)
- **Stale "processing" recovery** — if the async worker
  crashes, `run_status` stays "processing" with no
  automatic recovery mechanism

### Not Implemented

- **Scheduled auto-generation** — service method exists but
  no cron/scheduler invocation found
- **Concurrent run guard** — no database-level advisory
  lock; two users could start runs for the same month
  simultaneously
- **Currency validation** — `currency.upper()` applied but
  no whitelist; arbitrary strings accepted

---

## Data Model

| Entity | Table | Key Fields |
|---|---|---|
| ScheduleRun | `schedule_runs` | id, target_year, target_month, currency, include_inactive, run_status, processing_progress, error_message, pay_config_id, export_path, summary_* |
| Payout | `payouts` | id, schedule_run_id (FK), model_id (FK), pay_date, code, amount, status, is_locked, gross_amount, notes |
| ValidationIssue | `validation_issues` | id, schedule_run_id (FK), model_id (FK), severity, issue |
| ScheduleAmendment | `schedule_amendments` | id, schedule_run_id (FK), amendment_type, affected_codes, details |
| PayConfig | `pay_configs` | id (referenced by ScheduleRun.pay_config_id) |
| FrequencyPlan | `frequency_plans` | id (used by payroll engine for custom pay schedules) |
| PayoutCompensationAlert | `payout_compensation_alerts` | id, schedule_run_id (FK), payout_id (FK) |
| PayoutAdvanceAllocation | `payout_advance_allocations` | id (tracks advance deductions per payout) |

**Constraints:**

- `UniqueConstraint("schedule_run_id", "model_id", "pay_date")` on
  payouts — prevents duplicate payouts per model per date per run
- `CheckConstraint("amount_monthly > 0")` on models
- Cascade deletes: run deletion cascades to payouts,
  validations, alerts, amendments

---

## Lifecycle / State Behavior

```text
draft → processing → ready
                   ↘ error
```

- **draft**: created by `create_schedule_run`, no payouts
  yet
- **processing**: set when async worker starts; progress
  tracked via `processing_progress` (0-100)
- **ready**: set after payroll engine completes and payouts
  are stored
- **error**: set if `_payroll_background_worker` catches
  an exception; `error_message` populated

**Gap**: No recovery from stale "processing" (server crash
leaves run stuck).

---

## API / Services / Jobs

### Routes (35 total)

| Method | Path | Purpose |
|---|---|---|
| GET | `/schedules/` | Dashboard |
| GET | `/schedules/all` | All payouts cross-run |
| GET | `/schedules/combined-payouts` | Combined payouts view |
| GET | `/schedules/adhoc` | Adhoc payments list |
| GET | `/schedules/new` | Create form |
| POST | `/schedules/new` | Run schedule (sync) |
| POST | `/schedules/new/async` | Run schedule (async) |
| GET | `/schedules/{run_id}` | Run detail |
| GET | `/schedules/{run_id}/status` | Poll processing status |
| POST | `/schedules/{run_id}/refresh` | Refresh schedule |
| POST | `/schedules/{run_id}/add-new-models` | Add new models |
| POST | `/schedules/{run_id}/delete` | Delete run |
| POST | `/schedules/{run_id}/export` | Export CSV |
| POST | `/schedules/{run_id}/export-models` | Export models CSV |
| GET | `/schedules/{run_id}/download/{filename}` | Download export |
| POST | `/schedules/{run_id}/payouts/{id}/status` | Update payout status |
| POST | `/schedules/{run_id}/payouts/{id}/notes` | Update payout notes |
| POST | `/schedules/{run_id}/payouts/{id}/lock` | Lock payout |
| POST | `/schedules/{run_id}/payouts/{id}/unlock` | Unlock payout |
| POST | `/schedules/{run_id}/batch/status` | Bulk status change |
| POST | `/schedules/{run_id}/batch/lock` | Bulk lock |
| POST | `/schedules/{run_id}/batch/unlock` | Bulk unlock |

*(Plus additional helper/partial endpoints for HTMX.)*

### Service methods (`PayrollService`)

- `run_payroll` — synchronous full run
- `run_payroll_async` — background thread run
- `_run_payroll_inner` — core orchestration
- `add_new_models_to_run` — safe additive operation
- `_to_record` — model → ModelRecord conversion
- `auto_generate_upcoming_schedules` — batch creation

### Background job

- `_payroll_background_worker` thread — runs
  `_run_payroll_inner` with its own DB session, updates
  progress, catches errors

---

## UI Components

| Template | Purpose |
|---|---|
| `schedules/list.html` | Dashboard with run cards |
| `schedules/detail.html` | Run detail + payout table |
| `schedules/form.html` | Create/run schedule form |
| `schedules/all.html` | All payouts view |
| `schedules/all_table.html` | HTMX payout table partial |
| `schedules/combined_payouts.html` | Cross-run combined |
| `schedules/adhoc.html` | Adhoc payments |

---

## Dependencies / Integrations

- **Models module** — `crud.list_models` provides model
  data for payroll calculation
- **Cash advances** — advance allocations applied during
  payroll via `_apply_advance_allocations_for_run`
- **Compensation adjustments** — adjustments loaded per
  model and applied in `_to_record`
- **Core payroll engine** — `app/core/payroll.py`
  (`build_pay_schedule`, `validate_row`, etc.)
- **Export module** — `app/exporting/outputs.py`
  (`export_outputs`)
- **Auth** — `get_current_user` (view), `get_admin_user`
  (mutations)

---

## Known Issues

### CRITICAL — Path Traversal in Export

`output_dir` is a user-controlled `Form()` parameter
passed directly to `Path(output_dir).mkdir(parents=True)`.
A malicious admin could write exports to arbitrary
directories.

**Location**: `routers/schedules.py` L2176-2177, L2231-2232

**Fix**: Validate that the resolved path stays within the
project root, or remove the form parameter and hardcode
`DEFAULT_EXPORT_DIR`.

### HIGH — Stale "processing" Recovery

If the background worker thread crashes or the server
restarts, `run_status` stays "processing" forever. No
startup sweep or timeout mechanism exists.

**Location**: `services.py` `run_payroll_async`,
`_payroll_background_worker`

**Fix**: Add a startup check that resets runs stuck in
"processing" older than N minutes, or add a TTL.

### MEDIUM — No Concurrent-Run Guard

Two admins can start payroll runs for the same month
simultaneously. The existing-run check in
`_run_payroll_inner` is not atomic.

**Location**: `services.py` L126-160

**Fix**: Use `SELECT ... FOR UPDATE` or a DB advisory lock.

### LOW — No Currency Whitelist

`currency = currency.upper()` accepts any string.
Should validate against a known list (USD, EUR, etc.).

---

## Next Priority Tasks

1. **Fix path traversal** — hardcode export dir or validate
   path (CRITICAL security)
2. **Add stale-processing recovery** — startup sweep or
   timeout in status polling
3. **Add concurrent-run guard** — DB-level locking for
   same-month runs
4. **Extend filter preservation** — apply to refresh and
   bulk-action redirects, not just Add New Models
5. **Wire up auto-generation** — add scheduler/cron for
   `auto_generate_upcoming_schedules`
