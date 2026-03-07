# PayrollDeskAI — System Overview (Technical Deep Dive)

> Generated: 2026-03-08 | Version: 2.44.0

---

## 1. What This System Does

PayrollDeskAI is a **web-based payroll management application** built for agencies that manage contractors/models. It automates recurring payroll schedules, tracks commission referrals, handles cash advances, and provides a full dashboard for financial oversight.

**Core capabilities:**

- **Model management** — Contractor records with payment details, compensation history, soft-delete support
- **Payroll scheduling** — Generate payroll runs by month with weekly, biweekly, or monthly frequency plans
- **Commission system** — Referral-based commissions with configurable duration (1–36 months) and payout frequency
- **Cash advances** — Request → approve → automatic deduction from future payouts (with safety guardrails)
- **Ad-hoc payments** — One-off payments outside the regular schedule
- **Import/export** — Bulk CSV/Excel import and export for models, payouts, adjustments
- **Dashboard analytics** — KPIs, payment trends, donut charts, sparklines, top-model rankings
- **Audit trail** — Login attempts, admin action logs
- **User management** — Admin/user roles, account lockout after failed logins

---

## 2. Tech Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| Framework | **FastAPI** (ASGI) | Lifespan handler for startup, `CacheControlMiddleware` for static asset caching |
| ORM | **SQLAlchemy 2.0+** | `Mapped[]` type annotations, `mapped_column()`, `selectinload()` for eager loading |
| Database | **PostgreSQL** (prod) / **SQLite** (dev) | Dual engine support via `PAYROLL_DATABASE_URL` env var; SQLite FK enforcement via PRAGMA listener |
| Migrations | **Alembic** | 4 migration versions, auto-run on container startup via `entrypoint.sh` |
| Templates | **Jinja2 + HTMX** | Server-rendered HTML; custom Jinja2 filters (`money`, `display_date`, `display_datetime`); HTMX for partial page updates |
| Frontend | **Bootstrap 5** | BEM CSS methodology, custom SVG stroke icons (no image dependencies), shimmer skeleton loaders |
| Auth | **bcrypt** | `User.hash_password()` / `verify_password()` class methods; plain session cookies |
| Data Processing | **pandas** + **openpyxl** | DataFrame pipeline for payroll math; Excel I/O for import/export |
| Testing | **pytest** + pytest-cov | 50+ test files, temp SQLite per session, auto-clean domain tables between tests |
| Server | **Uvicorn** (dev) / **Gunicorn** (prod) | Gunicorn with uvicorn workers in Docker |
| Rate Limiting | **slowapi** | Limiter instance in `core/rate_limiter.py`, currently only on `/models/export` (5/min) |
| Deployment | **Docker** → **Render** | `python:3.11-slim` base, free tier, health check at `/health` |

---

## 3. Application Architecture

```
Browser (HTML/HTMX + Bootstrap 5)
          │
          ▼
┌──────────────────────────────────────────────────┐
│              FastAPI Application                  │
│                                                   │
│  Routers (8 files, ~73 endpoints)                │
│    auth · admin · models · schedules             │
│    dashboard · commissions · profile · changelog  │
│          │                                        │
│  Services & Business Logic                       │
│    services.py · commission.py                   │
│    core/payroll.py · core/formatting.py          │
│          │                                        │
│  CRUD Layer (crud.py — 95 functions, 2356 lines) │
│          │                                        │
│  SQLAlchemy ORM Models (models.py)               │
│  Pydantic Schemas (schemas.py)                   │
└──────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────┐
│  PostgreSQL / SQLite                              │
│  18 tables, FK constraints, Alembic migrations   │
└──────────────────────────────────────────────────┘
```

### Startup Sequence

1. `lifespan()` context manager calls `init_db()` — creates tables & seeds default admin user
2. `CacheControlMiddleware` added — hashed static files get 1-year immutable cache, non-hashed get 1-day
3. 8 routers mounted via `app.include_router()`
4. Static files mounted at `/static` → `app/static/`
5. Rate limiter state attached to `app.state.limiter`
6. Exception handler registered for `RateLimitExceeded`

### Request Flow

1. Request hits middleware (cache control headers for static, passthrough for API)
2. Router handler matched by path
3. `get_current_user()` dependency injects authenticated user (reads `user_id` from session cookie, queries DB)
4. `get_session()` dependency provides SQLAlchemy `Session` (auto-closed after request)
5. Handler calls service layer or CRUD directly
6. Jinja2 template rendered (HTML routes) or JSON returned (API routes)

---

## 4. Complete Database Schema

### 4.1 Entity Details

#### `users` (Auth)
```
id               INTEGER PK AUTO
username         VARCHAR(100) UNIQUE NOT NULL
password_hash    VARCHAR(255) NOT NULL          -- bcrypt hash
role             VARCHAR(50) DEFAULT 'user'     -- 'admin' | 'user'
is_locked        BOOLEAN DEFAULT FALSE
locked_until     DATETIME NULLABLE
failed_login_count INTEGER DEFAULT 0
last_failed_login  DATETIME NULLABLE
created_at       DATETIME DEFAULT now()
```

#### `models` (Core Entity)
```
id                          INTEGER PK AUTO
status                      VARCHAR(20) NOT NULL DEFAULT 'Active'     -- CHECK: Active|Inactive
code                        VARCHAR(50) UNIQUE NOT NULL               -- Business identifier
real_name                   VARCHAR(200) NOT NULL
working_name                VARCHAR(200) NOT NULL
start_date                  DATE NOT NULL
payment_method              VARCHAR(100) NOT NULL
payment_frequency           VARCHAR(20) NOT NULL                      -- weekly|biweekly|monthly
amount_monthly              NUMERIC(12,2) NOT NULL                    -- CHECK: > 0
crypto_wallet               VARCHAR(200) NULLABLE
created_at                  DATETIME DEFAULT now()
updated_at                  DATETIME DEFAULT now(), ON UPDATE now()
deleted_at                  DATETIME NULLABLE INDEX                   -- Soft delete marker

-- Commission fields (on the model itself)
referred_by_model_id        INTEGER FK→models.id ON DELETE SET NULL
commission_active           BOOLEAN DEFAULT FALSE
commission_per_referral     NUMERIC(12,2) NULLABLE
commission_payout_frequency VARCHAR(20) DEFAULT 'dual'                -- monthly|mid_month|dual
commission_duration_months  INTEGER NULLABLE                          -- CHECK: NULL OR > 0
commission_status           VARCHAR(20) DEFAULT 'unpaid'              -- CHECK: paid|unpaid
```

**Self-referential relationships:**
- `referred_by` → parent model (many-to-one, `uselist=False`)
- `referrals` → child models (one-to-many, via `referred_by_model_id`)

#### `model_referral_terms` (Commission Config)
```
id                          INTEGER PK AUTO
referrer_model_id           INTEGER FK→models.id CASCADE NOT NULL INDEX
referral_model_id           INTEGER FK→models.id CASCADE NOT NULL UNIQUE
commission_per_referral     NUMERIC(12,2) DEFAULT 0     -- CHECK: >= 0
commission_payout_frequency VARCHAR(20) DEFAULT 'dual'
commission_duration_months  INTEGER NULLABLE              -- CHECK: NULL OR > 0
is_active                   BOOLEAN DEFAULT TRUE

UNIQUE(referrer_model_id, referral_model_id)
```
This table decouples commission terms from the model itself, allowing per-referral configuration. The `referral_model_id` UNIQUE constraint means each model can only be referred by one referrer.

#### `model_compensation_adjustments`
```
id              INTEGER PK AUTO
model_id        INTEGER FK→models.id CASCADE NOT NULL INDEX
effective_date  DATE NOT NULL
amount_monthly  NUMERIC(12,2) NOT NULL     -- CHECK: > 0
notes           TEXT NULLABLE
created_at      DATETIME DEFAULT now()
created_by      VARCHAR(100) NULLABLE

UNIQUE(model_id, effective_date)           -- One adjustment per model per date
```

#### `schedule_runs`
```
id                       INTEGER PK AUTO
target_year              INTEGER NOT NULL
target_month             INTEGER NOT NULL
currency                 VARCHAR(10) DEFAULT 'USD'
include_inactive         BOOLEAN DEFAULT FALSE
summary_models_paid      INTEGER DEFAULT 0
summary_total_payout     NUMERIC(14,2) DEFAULT 0
summary_frequency_counts TEXT DEFAULT '{}'       -- JSON string: {"Weekly": 4, "Monthly": 2}
created_at               DATETIME DEFAULT now()
export_path              VARCHAR(255) DEFAULT 'exports'
```

#### `payouts`
```
id                INTEGER PK AUTO
schedule_run_id   INTEGER FK→schedule_runs.id CASCADE NOT NULL INDEX
model_id          INTEGER FK→models.id SET NULL NULLABLE INDEX
pay_date          DATE NOT NULL
code              VARCHAR(50) NOT NULL          -- Denormalized from model
real_name         VARCHAR(200) NOT NULL
working_name      VARCHAR(200) NOT NULL
payment_method    VARCHAR(100) NOT NULL
payment_frequency VARCHAR(20) NOT NULL
amount            NUMERIC(12,2) NOT NULL        -- NET amount (after advance deductions)
notes             TEXT NULLABLE
status            VARCHAR(20) DEFAULT 'not_paid' -- paid|approved|on_hold|not_paid

INDEX(schedule_run_id, status)
INDEX(schedule_run_id, model_id)
```

**Key design decision:** Payout rows denormalize model fields (`code`, `real_name`, etc.) at creation time. This means payouts preserve the model's state at generation time even if the model is later edited.

#### `model_advances` (Cash Advance)
```
id                INTEGER PK AUTO
model_id          INTEGER FK→models.id CASCADE NOT NULL INDEX
amount_total      NUMERIC(12,2) NOT NULL        -- CHECK: > 0
amount_remaining  NUMERIC(12,2) NOT NULL        -- CHECK: >= 0
status            VARCHAR(20) DEFAULT 'requested' -- requested|approved|active|closed
strategy          VARCHAR(20) DEFAULT 'fixed'   -- CHECK: fixed|percent
fixed_amount      NUMERIC(12,2) NULLABLE        -- Flat deduction per payout
percent_rate      NUMERIC(5,2) NULLABLE          -- CHECK: NULL OR [0, 100]
min_net_floor     NUMERIC(12,2) DEFAULT 500     -- CHECK: >= 0
max_per_run       NUMERIC(12,2) DEFAULT 600     -- CHECK: >= 0
cap_multiplier    NUMERIC(5,2) DEFAULT 1.0       -- CHECK: >= 0
notes             TEXT NULLABLE
created_at        DATETIME
updated_at        DATETIME
activated_at      DATETIME NULLABLE
```

**Lifecycle:** `requested` → `approved` → `active` → `closed` (when `amount_remaining` hits 0)

#### `advance_repayments`
```
id          INTEGER PK AUTO
advance_id  INTEGER FK→model_advances.id CASCADE NOT NULL INDEX
payout_id   INTEGER FK→payouts.id SET NULL NULLABLE
amount      NUMERIC(12,2) NOT NULL     -- CHECK: > 0
source      VARCHAR(20) DEFAULT 'auto' -- auto|manual
created_at  DATETIME
```

#### `payout_advance_allocations`
```
id              INTEGER PK AUTO
schedule_run_id INTEGER FK→schedule_runs.id CASCADE NOT NULL INDEX
payout_id       INTEGER FK→payouts.id CASCADE NOT NULL INDEX
model_id        INTEGER FK→models.id CASCADE NOT NULL INDEX
advance_id      INTEGER FK→model_advances.id CASCADE NOT NULL INDEX
planned_amount  NUMERIC(12,2) NOT NULL     -- CHECK: > 0
created_at      DATETIME
```
This is the **planning** table — records how much will be deducted from each payout for each advance. Allocations are created during payroll generation and converted to actual `AdvanceRepayment` records when the payout is marked as "paid".

#### `commission_payouts`
```
id                  INTEGER PK AUTO
referrer_model_id   INTEGER FK NOT NULL
referral_model_id   INTEGER FK NOT NULL
pay_date            DATE NOT NULL
schedule_type       VARCHAR(20) NOT NULL    -- 'monthly' | 'mid-month'
amount              NUMERIC(12,2) NOT NULL
status              VARCHAR(20) DEFAULT 'unpaid' -- unpaid|paid
```

#### Other Tables
- `validation_issues` — severity (error/warning) + issue text, linked to schedule_run + model
- `login_attempts` — username, success flag, IP, user agent, timestamp (indexed for lockout queries)
- `audit_logs` — user_id, action string, details (JSON text), timestamp
- `adhoc_payments` — model_id, pay_date, amount (CHECK > 0), status (pending|paid|cancelled)
- `payout_compensation_alerts` — tracks when compensation changes affect existing payouts

### 4.2 Relationship Map

```
users ─────────────────────────────────────── audit_logs
                                                (user_id FK)

models ─┬── payouts ─────── payout_advance_allocations
        │    (1:N cascade)        (payout_id FK)
        │
        ├── model_compensation_adjustments
        │    (1:N cascade, ordered by effective_date)
        │
        ├── adhoc_payments (1:N cascade)
        │
        ├── model_advances ─── advance_repayments
        │    (1:N cascade)       (1:N cascade)
        │
        ├── validation_issues (1:N cascade)
        │
        ├── payout_compensation_alerts (1:N cascade)
        │
        ├── model_referral_terms (as referrer, 1:N cascade)
        │
        ├── model_referral_terms (as referral, 1:1 unique)
        │
        └── models (self-referential: referred_by ↔ referrals)

schedule_runs ─┬── payouts (1:N cascade)
               ├── validation_issues (1:N cascade)
               ├── payout_compensation_alerts (1:N cascade)
               └── payout_advance_allocations (1:N cascade)
```

---

## 5. Authentication & Authorization

### Implementation (`app/auth.py`, `app/security.py`)

**User model:**
- Password hashed with `bcrypt.gensalt()` + `bcrypt.hashpw()`
- Verification via `bcrypt.checkpw()`
- Factory method: `User.create_user(username, password, role)`

**Session management:**
- Login sets `request.session["user_id"] = user.id`
- `get_current_user(request, db)` reads session, queries `User` by ID
- No cookie signing, no HMAC — raw integer in session store

**Account lockout (`app/security.py`):**
- Constants: `MAX_FAILED_ATTEMPTS = 5`, `LOCKOUT_DURATION_MINUTES = 15`
- `record_login_attempt()` — creates `LoginAttempt` row on every login attempt
- `get_failed_attempts_count()` — counts failed attempts within the last 15 minutes
- `is_account_locked()` — checks `User.is_locked` flag and `locked_until` timestamp
- Admin can bulk-unlock via `/admin/maintenance/unlock-accounts`

**Role enforcement:**
- Routes check `current_user.is_admin()` for admin-only endpoints
- No middleware-level role checking — each route handles its own authorization

### Security Gaps

| Issue | Severity | Detail |
|-------|----------|--------|
| Unsigned session cookie | High | `user_id` in session is a plain integer — can be forged if cookie secret is weak/missing |
| No CSRF protection | High | All POST endpoints accept requests without CSRF tokens |
| Sparse rate limiting | Medium | Only `/models/export` has `@limiter.limit("5/minute")`; login has account lockout but no IP-based rate limit |
| Naive datetimes | Low | `datetime.now()` throughout — no UTC, no timezone awareness |

---

## 6. Payroll Calculation Engine — Technical Detail

### 6.1 Data Pipeline (`app/core/payroll.py`)

**Core data structure:**
```python
@dataclass
class ModelRecord:
    row_number: int
    status: str                    # "Active" | "Inactive"
    code: str                      # Unique business identifier
    real_name: str
    working_name: str
    start_date: Optional[date]
    payment_method: str
    payment_frequency: str         # "weekly" | "biweekly" | "monthly"
    amount_monthly: Optional[Decimal]
    compensation_adjustments: List[tuple[date, Decimal]]  # [(effective_date, amount)]
    validation_messages: List[ValidationMessage]
```

**Frequency plans — fixed pay dates per month:**
```python
FREQUENCY_PLANS = {
    "weekly":   [0, 1, 2, 3],   # 4 paydays → 7th, 14th, 21st, last day
    "biweekly": [1, 3],          # 2 paydays → 14th, last day
    "monthly":  [3],             # 1 payday → last day of month
}
```

**Pay date generation:**
```python
def get_pay_dates(year, month):
    eom = calendar.monthrange(year, month)[1]
    return [date(year, month, 7), date(year, month, 14),
            date(year, month, 21), date(year, month, eom)]
```

The 4 fixed dates per month are: **7th, 14th, 21st, last day**. Frequency plans index into this array.

### 6.2 Amount Allocation

`allocate_amounts(monthly_amount, frequency)` splits the monthly salary across plan paydays:

```
Monthly $4000, frequency=weekly (4 paydays):
  base_share = $4000 / 4 = $1000.00 each
  
Monthly $1000, frequency=biweekly (2 paydays):
  base_share = $1000 / 2 = $500.00 each

Rounding adjustment: last payout absorbs any cent remainder
  e.g., $1000 / 3 = $333.33, $333.33, $333.34 (remainder goes to last)
```

### 6.3 Compensation Adjustment Resolution

`resolve_monthly_amount(record, pay_date)` applies time-sensitive salary changes:

```python
# Adjustments: [(2026-01-01, $5000), (2026-03-15, $6000)]
# For pay_date 2026-02-14: returns $5000 (latest adjustment before date)
# For pay_date 2026-04-07: returns $6000
# For pay_date 2025-12-21: returns model.amount_monthly (base, no adjustment active)
```

Adjustments are sorted by `effective_date` ascending. The last adjustment where `effective_date <= pay_date` wins. If no adjustment applies, the model's base `amount_monthly` is used.

### 6.4 Validation Rules

`validate_row()` returns a list of `ValidationMessage(level, text)`:

| Field | Rule | Level |
|-------|------|-------|
| `status` | Required, must be "Active" or "Inactive" | error |
| `status` | If not "Active", payouts suppressed | warning |
| `code` | Required | error |
| `real_name` | Should not be blank | warning |
| `working_name` | Should not be blank | warning |
| `payment_method` | Should not be blank | warning |
| `payment_frequency` | Required, must be weekly/biweekly/monthly | error |
| `amount_monthly` | Required, must be > 0 | error |
| `start_date` | Required, must be parseable | error |

Records with **any error-level message** are excluded from payout generation (`has_errors` property).

### 6.5 Schedule Generation Flow

`build_pay_schedule(records, year, month, currency)`:

1. Get 4 pay dates for the month
2. For each record without errors:
   a. Get the frequency plan indices
   b. For each plan index, get the pay date
   c. Resolve the effective monthly amount (base or adjusted)
   d. Divide by number of paydays: `monthly_amount / plan_length`
   e. Check eligibility: `record.start_date <= pay_date` and status == "Active"
   f. Emit a payout row with amount, date, model info
3. Return DataFrame + summary dict (`models_paid`, `total_payout`, `frequency_counts`)

### 6.6 Service Orchestration (`app/services.py` — `PayrollService`)

`run_payroll()` coordinates the full cycle:

1. **Idempotent re-run check:** If a `ScheduleRun` exists for (year, month), preserve old payout status/notes, clear old data, reuse the run ID
2. **Build records:** Convert each `Model` ORM object to a `ModelRecord`, attaching compensation adjustments
3. **Generate schedule:** Call `build_pay_schedule()` → DataFrame + summary
4. **Update run metadata:** `summary_models_paid`, `summary_total_payout`, `summary_frequency_counts` (JSON)
5. **Store payouts:** `crud.store_payouts()` — creates `Payout` rows, restores old status/notes by matching `(code, pay_date)` keys
6. **Apply advance allocations:** `_apply_advance_allocations_for_run()` — plans deductions, reduces payout `amount` (net)
7. **Store validations:** Persist `ValidationIssue` rows
8. **Export files:** Generate CSV/Excel in `exports/` directory with gross/deducted/net columns

**Add-new-models flow** (`add_new_models_to_run()`):
- Safe append-only operation — never modifies existing payouts
- Finds models not yet in the schedule, generates payouts only for them
- Returns count and codes of added models

---

## 7. Cash Advance System — Technical Detail

### 7.1 Advance Lifecycle

```
requested → approved → active → closed
                         │
                    [auto-deductions from payouts reduce amount_remaining]
                         │
                    amount_remaining == 0 → auto-close
```

### 7.2 Deduction Strategies

| Strategy | How it works |
|----------|-------------|
| `fixed` | Deduct `fixed_amount` from each payout (e.g., $200/payout) |
| `percent` | Deduct `percent_rate`% of the gross payout amount (e.g., 10% of $1000 = $100) |

### 7.3 Policy Knobs (per-advance overrides)

| Knob | Default | Purpose |
|------|---------|---------|
| `min_net_floor` | $500 | Minimum net payout after deduction (currently not enforced in allocation logic) |
| `max_per_run` | $600 | Maximum deduction per payroll run |
| `cap_multiplier` | 1.0 | Multiplier cap on total advance |

### 7.4 Allocation Algorithm (`_apply_advance_allocations_for_run`)

For each model with active advances, payouts are processed sequentially by `(pay_date, id)`:

```
For each payout (sorted by date):
  available = payout.amount (gross)
  For each active advance (sorted by created_at, oldest first):
    if advance has remaining balance:
      if strategy == fixed:  candidate = fixed_amount
      if strategy == percent: candidate = payout.amount * (percent_rate / 100)
      planned = min(candidate, advance.remaining, available - already_deducted)
      if planned > 0:
        payout.amount -= planned         # Reduce to net
        create PayoutAdvanceAllocation row
        track temp remaining per advance
```

**Key behaviors:**
- Allocations are **planning rows** — they don't reduce `advance.amount_remaining` yet
- When a payout is marked "paid" → `_realize_allocations_for_paid_payout()` converts allocations to actual `AdvanceRepayment` records and reduces `amount_remaining`
- Clearing/re-running a schedule purges old allocations (idempotent)
- Multiple advances per model are processed oldest-first

---

## 8. Commission System — Technical Detail

### 8.1 Data Model

There are two layers of commission config:

1. **On the `Model` itself:** `commission_active`, `commission_per_referral`, `commission_payout_frequency`, `commission_duration_months` — legacy/simple config
2. **`ModelReferralTerm` table:** Per-referral configuration (amount, frequency, duration, active flag) — preferred, decoupled from model

The `ModelReferralTerm.referral_model_id` has a UNIQUE constraint = each model can only be referred once.

### 8.2 Schedule Generation (`commission.py`)

`generate_referral_schedule(db, months_forward=3, today=None)`:

1. Find all models that have at least one active referral term
2. For each referrer, get eligible (active) referrals
3. For each referral with an active term:
   a. Determine commission windows based on frequency
   b. Generate payment dates for `months_forward` months
   c. Check if a `CommissionPayout` record exists for `(referrer_id, referral_id, pay_date, schedule_type)`
   d. If not, auto-create one with status "unpaid"
4. Sort all entries by `(pay_date, referrer_name, referral_name)`
5. Return list of `ReferralScheduleEntry` objects

**Frequency windows:**
```python
# "monthly"  → payouts on 1st of each month
# "mid_month" → payouts on 14th of each month  
# "dual"     → both 1st AND 14th
```

**Payment date iteration:**
- Anchor: `max(accepted_on, today)`, rounded to 1st of month
- For each month offset (0 to `months_forward - 1`):
  - If "monthly" allowed and `1st >= accepted_on and >= today`: yield `(1st, "monthly")`
  - If "mid-month" allowed and `14th >= accepted_on and >= today`: yield `(14th, "mid-month")`

### 8.3 Commission Summary

`build_commission_summary(db, referrer)` computes display-only stats:
- Count total and active referrals
- For each active referral with a positive commission amount:
  - Multiply `commission_per_referral × number_of_windows_per_month`
  - Sum into `estimated_monthly_commission`

---

## 9. Import/Export — Technical Detail

### 9.1 Excel Import (`app/importers/excel_importer.py`)

**Column resolution system:**
- Each importable field has a list of `aliases` (e.g., "code" matches "code", "model code", "model")
- `resolve_column()` does case-insensitive matching against DataFrame column headers
- Missing required columns raise `ValueError`

**Supported sheets and their columns:**

| Sheet | Required Columns | Optional Columns |
|-------|------------------|-----------------|
| Models | code, real_name, working_name, start_date, payment_method, payment_frequency, amount_monthly | status, crypto_wallet |
| Payouts | code, pay_date, amount, status | payment_method, payment_frequency, notes |
| CompensationAdjustments | code, effective_date, amount_monthly | notes |
| Adhoc | code, pay_date, amount | status, description, notes |

**Date parsing cascade:**
1. Check if already a `date` or `datetime` object
2. Try `mm/dd/yyyy`, `yyyy-mm-dd`, `mm-dd-yyyy` format strings
3. Fall back to `dateutil.parser.parse()` (very flexible)

**Decimal parsing:**
- Strip whitespace, convert via `Decimal(str(value))`
- Invalid values raise with field name context

**Import options:**
```python
@dataclass
class ImportOptions:
    model_sheet: str = "Models"
    payout_sheet: str = "Payouts"
    update_existing: bool = False          # If True, update matching models by code
    adjustments_sheet: str | None = "CompensationAdjustments"
    adhoc_sheet: str | None = "Adhoc"

@dataclass
class RunOptions:
    schedule_run_id: int | None = None     # Attach payouts to existing run
    create_schedule_run: bool = False      # Create new run for imported payouts
    target_year/month: int | None = None
    auto_generate_runs: bool = False       # Group by month and auto-create runs
```

### 9.2 Excel Export (`app/exporting/xlsx.py`)

Generates multi-sheet workbooks using pandas + openpyxl:

- **Models sheet:** All current model records with amounts, dates, wallet info
- **Payouts sheet:** For a specific run — includes gross, advances deducted, net columns
- **Adjustments sheet:** All compensation adjustments with model codes
- **Adhoc sheet:** All ad-hoc payments with statuses
- **Runs sheet:** Schedule run metadata

The export during payroll generation includes net vs gross breakdown:
```
Amount Gross (USD) | Advances Deducted (USD) | Amount Net (USD) | Status
$1,000.00          | $200.00                  | $800.00          | Not Paid
```

---

## 10. CRUD Layer (`app/crud.py`) — 95 Functions

### 10.1 Patterns

**Filtering:** `_model_filters()` builds SQLAlchemy `where` clauses from optional params, using `ilike` for text search
**Soft delete:** `deleted_at` timestamp on `Model`; `list_models()` excludes deleted by default (`include_deleted=False`)
**Eager loading:** `selectinload()` used when accessing relationships to avoid N+1 queries (e.g., `selectinload(ScheduleRun.payouts)`)
**Pagination:** `limit` + `offset` params on list queries

### 10.2 Function Groups

| Domain | Count | Key Functions |
|--------|-------|---------------|
| **Models** | 15+ | `list_models`, `create_model`, `update_model`, `soft_delete_model`, `restore_model`, `get_model_by_code` |
| **Referral Terms** | 3 | `list_referral_terms`, `upsert_referral_terms` |
| **Compensation** | 2 | `create_compensation_adjustment`, `get_effective_compensation_amount` |
| **Schedule Runs** | 7 | `create_schedule_run`, `clear_schedule_data`, `list_schedule_runs`, `get_schedule_run` |
| **Payouts** | 8 | `store_payouts`, `list_payouts_for_run`, `update_payout`, `payout_codes_for_run` |
| **Validation** | 3 | `store_validation_messages`, `list_validation_for_run` |
| **Dashboard** | 8 | `dashboard_summary`, `top_paid_models_comprehensive`, `run_payment_summary` |
| **Ad-hoc** | 7 | `create_adhoc_payment`, `update_adhoc_payment`, `delete_adhoc_payment` |
| **Advances** | 10+ | `create_advance`, `approve_advance`, `record_advance_repayment`, `_apply_advance_allocations_for_run`, `_realize_allocations_for_paid_payout` |
| **Admin** | 10 | `purge_model_hard`, `log_admin_action`, `cleanup_empty_runs`, `reset_application_data` |

### 10.3 Key Implementation Details

**`store_payouts()`** — Preserves status/notes from previous runs:
```python
# Old payout data keyed by (code, pay_date):
old_payout_data = {("M001", date(2026,3,14)): {"status": "paid", "notes": "Verified"}}
# When re-generating, matching keys restore the old status instead of defaulting to "not_paid"
```

**`_apply_advance_allocations_for_run()`** — See Section 7.4

**`_realize_allocations_for_paid_payout()`** — When payout status changes to "paid":
- Find all `PayoutAdvanceAllocation` rows for this payout
- For each allocation, create an `AdvanceRepayment` (source="auto")
- Reduce `advance.amount_remaining`
- Auto-close advance if balance hits 0

**`dashboard_summary()`** — Single-query optimization:
- Groups model counts by status in one query
- Computes lifetime paid, outstanding, pending, on_hold via `case()` expressions
- Calculates monthly burn, run rate (annualized), year-to-date totals

---

## 11. Pydantic Schemas (`app/schemas.py`)

### Validation Rules

```python
class ModelBase(BaseModel):
    status: str       # Field(..., pattern="Active|Inactive"), then .title() normalized
    code: str         # min_length=1, max_length=50, stripped
    real_name: str    # min_length=1, max_length=200, stripped
    amount_monthly: Decimal  # gt=0, quantized to 0.01 (ROUND_HALF_UP)
    payment_frequency: str   # Lowercased, must be in FREQUENCY_ENUM
    commission_per_referral: Decimal | None  # ge=0, quantized to 0.01
    commission_payout_frequency: str  # Lowercased, must be in COMMISSION_PAYOUT_FREQUENCY_ENUM
    commission_duration_months: int | None  # ge=1, le=36
    commission_status: str  # Lowercased, must be in COMMISSION_STATUS_ENUM
```

**Validator chain (mode="before"):**
1. `strip_required_strings` — strips whitespace, rejects None/empty for code, real_name, working_name, payment_method
2. `ensure_start_date_present` — rejects None or empty string
3. `validate_frequency` — lowercases and checks against enum
4. `quantize_amount` — rounds to 2 decimal places

---

## 12. Database Layer (`app/database.py`)

### Engine Configuration

```python
DATABASE_URL = os.getenv("PAYROLL_DATABASE_URL", "sqlite:///data/payroll.db")

# PostgreSQL: connection pooling enabled by default (SQLAlchemy defaults)
# SQLite: connect_args={"check_same_thread": False} for FastAPI threading
```

### Event Listeners

1. **SQLite FK enforcement:** `PRAGMA foreign_keys=ON` on every connection (via `@event.listens_for(engine, "connect")`)
2. **Query logging:** When `LOG_QUERIES=true`, logs all queries with timing; warns on queries > 100ms
3. **URL masking:** `_mask_db_url()` redacts passwords in log output

### Session Management

```python
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```
Used as a FastAPI dependency via `Depends(get_session)`.

### Initialization

`init_db()`:
1. Create all tables from SQLAlchemy metadata
2. Check if any users exist
3. If none, create default admin: `username="admin"`, `password="admin123"`, `role="admin"`

---

## 13. Frontend Architecture

### Rendering Approach

- **Server-rendered HTML** via Jinja2 — no client-side framework
- **HTMX** for dynamic behavior — partial page swaps, form submissions without full reload
- **Bootstrap 5** for layout and components
- **Custom CSS** with **BEM methodology** in `app/static/css/styles.css`
- **Custom SVG icons** — stroke-based, embedded inline (no icon library dependency)

### Template Filters (`app/dependencies.py`)

| Filter | Function | Example |
|--------|----------|---------|
| `money` | Format as `$1,234.56` | `{{ amount \| money }}` |
| `display_date` | Format as `mm/dd/yyyy` | `{{ dt \| display_date }}` |
| `display_datetime` | Format as `mm/dd/yyyy hh:mm AM/PM` | `{{ dt \| display_datetime }}` |

### Global Template Variables

- `APP_VERSION` — from `app/__version__`
- `APP_NAME` — "Payroll Desk"

### UI Features

- Shimmer/skeleton loaders for async data
- Count-up animations on KPI numbers
- SVG donut chart for paid/unpaid ratio
- 6-month sparkline trend chart
- Focus trap utility for modal accessibility
- ARIA attributes (`aria-expanded`, `aria-labelledby`, `role="alert"`)
- Toast notification system (`showToast()`)

---

## 14. Deployment

### Docker (`Dockerfile`)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get install build-essential libpq-dev gcc curl  # For psycopg2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

**`entrypoint.sh`:** Runs `alembic upgrade head` (migrations), then starts `gunicorn` with uvicorn workers.

### Render (`render.yaml`)

```yaml
services:
  - type: web
    name: payroll-desk
    env: docker
    repo: mirabelleagency/PayrollDesk
    branch: main
    plan: free
    envVars:
      - key: PAYROLL_DATABASE_URL
        value: "<SET_IN_RENDER_UI>"
    healthCheckPath: /health
```

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `PAYROLL_DATABASE_URL` | No | `sqlite:///data/payroll.db` | Database connection string |
| `LOG_QUERIES` | No | `false` | Enable SQL query logging with timing |
| `PYTHONUNBUFFERED` | No | — | Set to `1` for Docker log flushing |

---

## 15. Testing Infrastructure

### Configuration (`conftest.py`, `pytest.ini`)

```ini
# pytest.ini
testpaths = tests
addopts = -v --tb=short
```

**Test database:** Temporary SQLite file per session (not in-memory, to support FK constraints)

**Fixture setup:**
1. Create engine pointing to temp file
2. Enable `PRAGMA foreign_keys=ON`
3. Create all tables
4. Seed default admin user
5. Between tests: truncate all domain tables but preserve `users`

### Test Coverage

50+ test files covering:
- Auth flows (login, lockout, session, redirect)
- CRUD operations (all domains)
- Route integration tests (auth required, form validation, HTMX responses)
- Payroll schedule generation
- Commission calculations
- Cash advance lifecycle
- Import/export roundtrips
- Dashboard queries
- Admin maintenance operations

---

## 16. Remaining Backlog

| Priority | Task | Category |
|----------|------|----------|
| Medium | CSS extraction for `schedules/detail.html` (52 inline styles) | Refactor |
| Medium | Add schedules router tests (currently ~40% coverage) | Testing |
| Low | Background tasks for exports | Performance |
| Low | Full-text search (PostgreSQL tsvector) | CRUD |
| Low | API versioning | API |
| Low | Split `schedules.py` into sub-modules (1097 lines) | Refactor |
| Low | CSS extraction for remaining templates (206 inline styles) | Refactor |
| Low | Dark/light theme toggle | UX |

---

## 17. File Structure

```
PayrollDeskAI/
├── app/
│   ├── __init__.py           # __version__ = "2.44.0"
│   ├── main.py               # FastAPI app, middleware, route mounting, health checks
│   ├── models.py             # SQLAlchemy ORM models (18 tables, all constraints/indexes)
│   ├── schemas.py            # Pydantic schemas with field validators
│   ├── crud.py               # 95 CRUD functions (2356 lines)
│   ├── services.py           # PayrollService — orchestrates payroll generation
│   ├── commission.py         # Commission calculation, schedule generation
│   ├── auth.py               # User model, bcrypt hash/verify
│   ├── security.py           # Login attempt recording, lockout logic
│   ├── database.py           # Engine creation, session factory, FK enforcement, query logging
│   ├── dependencies.py       # Jinja2 templates, filters, global template vars
│   ├── core/
│   │   ├── payroll.py        # ModelRecord, validation, pay date math, schedule building
│   │   ├── formatting.py     # display_date, display_datetime formatters
│   │   ├── config.py         # DEFAULT_CURRENCY = "USD", DEFAULT_LOCALE = "en-US"
│   │   └── rate_limiter.py   # slowapi Limiter instance
│   ├── routers/
│   │   ├── auth.py           # /login, /logout
│   │   ├── admin.py          # /admin/users, /admin/maintenance/*
│   │   ├── models.py         # /models CRUD, import, export, adhoc, adjustments
│   │   ├── schedules.py      # /schedules — payroll runs, payouts, alerts
│   │   ├── dashboard.py      # /dashboard, /api/dashboard/*, /api/recent-runs
│   │   ├── commissions.py    # /commissions — referral schedule, payout tracking
│   │   ├── profile.py        # /profile, change-password
│   │   └── changelog.py      # /changelog
│   ├── exporting/
│   │   └── xlsx.py           # Multi-sheet Excel + CSV export
│   ├── importers/
│   │   └── excel_importer.py # Column-alias-based Excel import with validation
│   ├── templates/            # Jinja2 HTML (base.html + subfolders per domain)
│   └── static/
│       ├── css/styles.css    # BEM-based custom styles
│       ├── dist/             # Bundled assets
│       └── import_templates/ # Sample Excel templates for import
├── tests/                    # 50+ pytest files
├── migrations/
│   ├── env.py                # Alembic environment config
│   └── versions/             # 4 migration scripts
├── scripts/                  # Utility scripts (debug, import, cleanup)
├── docs/                     # Project documentation
├── data/                     # SQLite database file (local dev)
├── exports/                  # Generated CSV/Excel files
├── samples/                  # Sample data files
├── conftest.py               # Test fixtures, temp DB, auto-cleanup
├── pytest.ini                # Test runner config
├── payroll.py                # CLI entry point
├── Dockerfile                # python:3.11-slim production container
├── entrypoint.sh             # Alembic migrate + gunicorn start
├── healthcheck.sh            # Container health check script
├── render.yaml               # Render deployment manifest
├── alembic.ini               # Alembic config (points to migrations/)
├── requirements.txt          # Python dependencies
├── CHANGELOG.md              # Version history
└── README.md                 # Project readme
```
