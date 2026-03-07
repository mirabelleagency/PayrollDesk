# Schedule System Revamp Plan

> **Branch:** payrolldesk-v4  
> **Goal:** Industry-standard payroll scheduling with auto-generation, calendar dashboard, and monthly reporting  
> **Approach:** Option C — Hybrid (rolling calendar + auto-generated drafts + monthly export/reports)

---

## Implementation Status

| Phase | Description | Status | Commit |
|-------|-------------|--------|--------|
| **Phase 1** | Database schema (PayConfig, FrequencyPlan, ScheduleAmendment models, Payout locking) | ✅ Done | `9c7f34d` |
| **Phase 2** | Config-driven engine (pay_days, frequency_plans params in payroll.py) | ✅ Done | `9c7f34d` |
| **Phase 3** | Selective refresh + payout locking (clear_unlocked_schedule_data, auto-lock on paid) | ✅ Done | `9c7f34d` |
| **Phase 4** | Auto-generation (auto_generate_upcoming_schedules, upcoming pay dates API) | ✅ Done | `277381f` |
| **Phase 5** | Calendar dashboard + run status UI (calendar strip, status badges, lock icons) | ✅ Done | `277381f` |
| **Phase 6** | Transaction safety (try/except rollback wrapper in run_payroll) | ✅ Done | `9c7f34d` |
| **Phase 7** | Admin settings UI for pay config & frequency plans | ✅ Done | `ecb64cc` |
| **Phase 8** | Amendment logging on refresh/add_models | ✅ Done | `ecb64cc` |
| **Phase 9** | Auto-resolve compensation alerts on recalculation | ✅ Done | `ecb64cc` |
| **Phase 10** | Background processing thread | ✅ Done | `88f9b8f` |

---

## Design Philosophy

**Current flow:** "I need to run payroll for January" (user-initiated)  
**New flow:** "January payroll is ready for your review" (system-initiated)

Like Gusto/ADP/Rippling — define pay schedule once, system auto-generates drafts, user reviews → approves → processes.

---

## What Changes

| Area | Current | Revamped |
|------|---------|----------|
| **Pay dates** | Hardcoded `[7, 14, 21, EOM]` | Configurable per-org via `PayConfig` table |
| **Frequency plans** | Hardcoded dict in `payroll.py` | Database-driven, editable via admin UI |
| **Schedule creation** | Manual "Run Payroll" per month | Auto-generated drafts for upcoming pay periods |
| **Dashboard** | Monthly schedule list | Rolling calendar: "Next 7/14/30 days" + month filter |
| **Schedule refresh** | Delete ALL payouts → rebuild from scratch | Selective: only recalculate unpaid/approved payouts |
| **Paid payout safety** | Entire schedule locked after 1 repayment | Per-payout locking: paid = immutable, rest refreshable |
| **Change tracking** | None (old data lost on refresh) | `ScheduleAmendment` log with before/after diff |
| **Advance allocations on refresh** | All cleared → re-applied | Only recalculate for unpaid payouts |
| **Compensation alerts** | Manual resolution only | Auto-resolve when payout recalculated to new amount |
| **Run processing** | Synchronous (blocks UI) | Transaction-safe with full rollback |
| **Error handling** | No rollback on mid-run failure | Transaction-safe with full rollback |
| **Reporting** | Monthly CSV/Excel export only | Monthly + custom date range + on-demand reports |

---

## Phase 1: Database Schema

### New Tables

#### `pay_configs` — Configurable pay dates & defaults
```
id              INTEGER PRIMARY KEY
name            VARCHAR(100)  -- "Default", "Custom Q1", etc.
pay_days        TEXT          -- JSON: [7, 14, 21, "eom"]
currency        VARCHAR(10)   -- Default currency
is_default      BOOLEAN       -- Only one can be default
created_at      DATETIME
updated_at      DATETIME
```

#### `frequency_plans` — Database-driven frequency definitions
```
id              INTEGER PRIMARY KEY
name            VARCHAR(50)   -- "weekly", "biweekly", "monthly", "semimonthly"
pay_day_indices TEXT          -- JSON: [0,1,2,3] / [1,3] / [3]
display_name    VARCHAR(100)  -- "Weekly (4x/month)", etc.
is_active       BOOLEAN
created_at      DATETIME
```

#### `schedule_amendments` — Change tracking log
```
id              INTEGER PRIMARY KEY
schedule_run_id INTEGER FK
amendment_type  VARCHAR(30)   -- "refresh", "add_models", "manual_edit"
models_affected TEXT          -- JSON: ["CODE1", "CODE2"]
changes_summary TEXT          -- JSON: [{code, field, old, new}, ...]
created_by      VARCHAR(100)
created_at      DATETIME
```

### Modified Tables

#### `schedule_runs` — add config reference
```
+ pay_config_id   INTEGER FK    -- Which pay config was used
+ status          VARCHAR(20)   -- "processing" | "ready" | "error"
+ error_message   TEXT          -- If status = "error"
+ processing_progress INTEGER   -- 0-100 percentage
```

#### `payouts` — add locking
```
+ is_locked       BOOLEAN DEFAULT FALSE  -- Immutable once paid
+ gross_amount    NUMERIC(12,2)          -- Original calculated amount (before advances)
```

---

## Phase 2: Core Engine Changes

### `app/core/payroll.py`

**Config-driven pay dates:**
```python
# BEFORE (hardcoded)
def get_pay_dates(year, month):
    return [date(year, month, 7), date(year, month, 14), ...]

# AFTER (config-driven)
def get_pay_dates(year, month, pay_days=None):
    if pay_days is None:
        pay_days = [7, 14, 21, "eom"]
    eom = calendar.monthrange(year, month)[1]
    return [date(year, month, eom if d == "eom" else d) for d in pay_days]
```

**Config-driven frequency plans:**
```python
# BEFORE (hardcoded dict)
FREQUENCY_PLANS = {"weekly": [0,1,2,3], "biweekly": [1,3], "monthly": [3]}

# AFTER (loaded from DB, with fallback)
_DEFAULT_PLANS = {"weekly": [0,1,2,3], "biweekly": [1,3], "monthly": [3]}

def get_frequency_plans(db_plans=None):
    if db_plans:
        return {p.name: json.loads(p.pay_day_indices) for p in db_plans}
    return _DEFAULT_PLANS
```

**Selective record building:**
```python
def build_pay_schedule_for_models(
    records, year, month, currency, pay_days=None, frequency_plans=None
):
    """Same as build_pay_schedule but accepts config parameters."""
    pay_dates = get_pay_dates(year, month, pay_days)
    plans = frequency_plans or _DEFAULT_PLANS
    # ... rest of logic unchanged
```

---

## Phase 3: Service Layer Changes

### `app/services.py` — `PayrollService`

**Selective refresh (biggest change):**
```python
def run_payroll(self, ...):
    existing_runs = crud.list_schedule_runs(...)
    
    if existing_runs:
        run = existing_runs[0]
        # ONLY clear unlocked (unpaid) payouts
        crud.clear_unlocked_payouts(self.db, run)
        # Preserve locked (paid) payout codes
        locked_codes = crud.get_locked_payout_codes(self.db, run.id)
    else:
        run = crud.create_schedule_run(...)
        locked_codes = set()
    
    # Only recalculate for non-locked models
    models = [m for m in crud.list_models(self.db) if m.code not in locked_codes]
    records = [self._to_record(...) for model in models]
    
    schedule_df, summary = build_pay_schedule(records, ...)
    
    # Store only new payouts (locked ones untouched)
    crud.store_payouts(self.db, run, payout_records, ...)
    
    # Log amendment
    crud.create_amendment(self.db, run, "refresh", affected_codes, changes)
```

**Transaction safety:**
```python
def run_payroll(self, ...):
    try:
        # All DB operations within existing session
        ... (all logic) ...
        self.db.commit()
    except Exception as e:
        self.db.rollback()
        run.status = "error"
        run.error_message = str(e)
        self.db.commit()
        raise
```

**Background processing (optional, phase 4+):**
```python
def run_payroll_async(self, ...):
    run = crud.create_schedule_run(self.db, ..., status="processing")
    self.db.commit()
    
    # Launch in background thread
    thread = threading.Thread(target=self._run_payroll_worker, args=(run.id, ...))
    thread.start()
    
    return run.id  # Caller polls for status
```

---

## Phase 4: CRUD Layer Changes

### `app/crud.py`

**New functions:**
```python
def clear_unlocked_payouts(db, run):
    """Delete only payouts where is_locked=False."""
    # Also clear their allocations
    # Leave locked payouts and their realized repayments intact

def get_locked_payout_codes(db, run_id):
    """Return set of model codes with locked (paid) payouts."""

def create_amendment(db, run, amendment_type, affected_codes, changes):
    """Log a schedule amendment for audit trail."""

def get_pay_config(db, config_id=None):
    """Get pay config by ID, or the default one."""

def list_frequency_plans(db):
    """Get all active frequency plans."""
```

**Modified functions:**
```python
def store_payouts(db, run, records, ..., locked_codes=None):
    """Skip storing for locked codes (they already exist)."""

def update_payout(db, payout, note, status):
    """When status → 'paid': set is_locked=True, then realize allocations."""
```

---

## Phase 5: Routes & UI

### Admin Settings Page
- Configure pay dates (drag/drop or form)
- Manage frequency plans (add/edit/disable)
- Set default currency

### Schedule Dashboard Improvements
- Show schedule status badge ("Processing...", "Ready", "Error")
- Show amendment history on schedule detail
- "Refresh" button only recalculates unlocked payouts
- Warning banner if some payouts are locked

### Schedule Detail Improvements
- Lock icon on paid/locked payouts
- "Locked" badge with tooltip explaining why
- Per-row refresh button for individual model recalculation
- Amendment log panel (expandable)

### Progress Indicator (if background processing)
- Animated progress bar during payroll run
- Real-time model count: "Processing 45/120 models..."
- Auto-redirect to detail page when complete

---

## Implementation Order

| Step | What | Files Changed | Risk | Status |
|------|------|---------------|------|--------|
| **1** | Transaction safety wrapper | `services.py` | Low | ✅ Done |
| **2** | Add `PayConfig` + `FrequencyPlan` models | `models.py`, migration | Low | ✅ Done |
| **3** | Config-driven `get_pay_dates()` | `payroll.py` | Low | ✅ Done |
| **4** | Config-driven frequency plans | `payroll.py` | Low | ✅ Done |
| **5** | Add `is_locked` + `gross_amount` to Payout | `models.py`, migration | Low | ✅ Done |
| **6** | Selective refresh (`clear_unlocked_payouts`) | `crud.py`, `services.py` | Medium | ✅ Done |
| **7** | Auto-lock on paid status | `crud.py` | Low | ✅ Done |
| **8** | Auto-generation + calendar dashboard | `services.py`, `schedules.py`, templates | Medium | ✅ Done |
| **9** | Run status + lock icons in UI | templates, CSS | Low | ✅ Done |
| **10** | `ScheduleAmendment` logging | `crud.py`, `services.py` | Low | ✅ Done |
| **11** | Admin settings UI for pay config | `routers/admin.py`, templates | Low | ✅ Done |
| **12** | Auto-resolve compensation alerts | `crud.py` | Low | ✅ Done |
| **13** | Background processing thread | `services.py` | Medium | ✅ Done |

---

## Backward Compatibility

- All new fields have defaults → existing data works unchanged
- `PayConfig` seeded with current `[7, 14, 21, "eom"]` on migration
- `FrequencyPlan` seeded with current `weekly/biweekly/monthly` plans
- `is_locked` defaults to `False` → existing payouts remain editable
- `gross_amount` backfilled from `amount + allocated` on migration
- Hardcoded fallbacks remain in `payroll.py` if no DB config exists

---

## What We're NOT Changing

- Payout model structure (still denormalized model snapshot per row)
- Advance two-phase workflow (allocate → realize)  
- Commission system (independent of payroll schedules)
- Export format (CSV/Excel with Gross/Net/Deducted)
- Authentication & authorization layer
- Dashboard cache mechanism (just improved invalidation)

---

## UI/UX Changes Summary

### Payroll Hub (`/schedules`)
1. **Upcoming Pay Dates Calendar Strip** — horizontal scrollable strip showing next 3 months of pay dates
   - Each card shows month abbreviation, day number, paid/total count, and total amount
   - Green border = schedule exists; dashed purple border = draft schedule; no border = no schedule yet
   - Clicking a card navigates to the run detail (or New Cycle form if none exists)
2. **Auto-Generate Drafts Button** — in calendar strip header, admin-only
   - Creates draft runs for next 2 months in one click
   - Redirects to the first newly created run
3. **Status Column in Cycles Table** — new column showing Draft / Ready / Processing / Error badges
   - Draft = purple chip, Ready = green chip, Processing = yellow chip, Error = red chip

### Schedule Detail (`/schedules/{id}`)
4. **Run Status Badge** — shown in the header next to cycle number (Draft / Ready / Processing / Error)
5. **Lock Icon (🔒)** — shown next to model code for payouts that are locked (paid)
   - Tooltip: "Locked — paid payout preserved on refresh"
   - Locked payouts are skipped during schedule refresh, preserving their data

### Behind the Scenes (no visible UI yet)
- **Selective refresh** — refreshing a cycle only recalculates unlocked payouts; paid payouts are preserved
- **Config-driven pay dates** — pay dates sourced from DB (PayConfig table) instead of hardcoded
- **Config-driven frequency plans** — frequency definitions from DB (FrequencyPlan table)
- **Transaction safety** — payroll run wrapped in try/except with rollback on failure

### Remaining UI Changes (Phase 7+)
- Admin settings page to configure pay dates and frequency plans
- Amendment history log panel on schedule detail
- Per-row refresh button for individual model recalculation
- Warning banner when some payouts in a run are locked
