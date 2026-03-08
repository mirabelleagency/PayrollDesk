# PayrollDesk Technical Specification

> Comprehensive technical documentation for the PayrollDesk payroll management system.

**Version:** 2.42.0
## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Database Schema](#database-schema)
5. [API Reference](#api-reference)
6. [Authentication & Security](#authentication--security)
7. [Core Business Logic](#core-business-logic)
8. [Data Flow Diagrams](#data-flow-diagrams)
9. [Configuration](#configuration)
10. [File Structure](#file-structure)

---

## System Overview

PayrollDesk is a web-based payroll management application designed to handle:

- **Model Management** - Track contractors/models with payment details
- **Payroll Scheduling** - Generate pay schedules based on payment frequency (weekly, biweekly, monthly)
- **Commission System** - Referral-based commission tracking and payouts
- **Cash Advances** - Request, approve, and track advance repayments
- **Adhoc Payments** - One-time payments outside regular schedules
- **Export/Import** - CSV/Excel import and export capabilities
- **Audit Trail** - Login attempts and action logging

### Key Features

| Feature | Description |
|---------|-------------|
| Multi-frequency Payroll | Supports weekly, biweekly, and monthly payment schedules |
| Soft Delete | Models can be deleted without losing historical data |
| Compensation History | Track salary changes over time with effective dates |
| Commission Tracking | Per-referral commissions with configurable duration |
| Account Lockout | Auto-lockout after failed login attempts |
| Dashboard Caching | In-memory caching with 5-minute TTL |
| Comprehensive Payment Totals | Aggregates payroll, adhoc, and commission payments for lifetime totals |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                         │
│                   HTML/CSS/JavaScript + HTMX                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │  Routers  │  │ Templates │  │  Static   │  │   Auth    │   │
│  │ (8 files) │  │  (Jinja2) │  │  Assets   │  │ Middleware│   │
│  └─────┬─────┘  └───────────┘  └───────────┘  └───────────┘   │
│        │                                                        │
│  ┌─────▼─────────────────────────────────────────────────────┐ │
│  │                    Service Layer                          │ │
│  │  PayrollService │ CommissionService │ AdvanceService      │ │
│  └─────────────────────────┬─────────────────────────────────┘ │
│                            │                                    │
│  ┌─────────────────────────▼─────────────────────────────────┐ │
│  │                     CRUD Layer                            │ │
│  │           app/crud.py (2034 lines, 86% coverage)          │ │
│  └─────────────────────────┬─────────────────────────────────┘ │
│                            │                                    │
│  ┌─────────────────────────▼─────────────────────────────────┐ │
│  │                   SQLAlchemy ORM                          │ │
│  │          Models │ Relationships │ Constraints             │ │
│  └─────────────────────────┬─────────────────────────────────┘ │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Database                                 │
│            PostgreSQL                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| **Routers** | `app/routers/*.py` | HTTP request handling, form validation, response rendering |
| **Services** | `app/services.py` | Business orchestration, complex workflows |
| **CRUD** | `app/crud.py` | Database operations, queries, data access |
| **Models** | `app/models.py` | SQLAlchemy ORM definitions, constraints |
| **Schemas** | `app/schemas.py` | Pydantic models for validation |
| **Core** | `app/core/payroll.py` | Payroll calculation logic |
| **Auth** | `app/auth.py`, `app/security.py` | Authentication, authorization, rate limiting |

---

## Technology Stack

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| **Framework** | FastAPI | Latest |
| **ORM** | SQLAlchemy | 2.0+ |
| **Database** | PostgreSQL | 14+ |
| **Migrations** | Alembic | Latest |
| **Template Engine** | Jinja2 | Latest |
| **Password Hashing** | bcrypt | Latest |
| **Data Processing** | pandas | Latest |
| **Date Parsing** | python-dateutil | Latest |

### Frontend

| Component | Technology |
|-----------|------------|
| **HTML Enhancement** | HTMX |
| **CSS Framework** | Bootstrap 5 |
| **Icons** | Custom SVG (stroke-based) |
| **Charts** | SVG donut, sparkline (no library) |

### Development & Testing

| Tool | Purpose |
|------|---------|
| pytest | Test framework |
| pytest-cov | Coverage reporting |
| Uvicorn | ASGI server |
| Alembic | Database migrations |

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐
│     users       │
├─────────────────┤
│ id (PK)         │
│ username        │
│ password_hash   │
│ role            │
│ is_locked       │
│ locked_until    │
│ failed_login_   │
│   count         │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     models      │       │  schedule_runs  │       │    payouts      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄──┐   │ id (PK)         │◄──────│ schedule_run_id │
│ status          │   │   │ target_year     │       │ model_id (FK)   │──┐
│ code (unique)   │   │   │ target_month    │       │ pay_date        │  │
│ real_name       │   │   │ currency        │       │ amount          │  │
│ working_name    │   │   │ include_inactive│       │ status          │  │
│ start_date      │   │   │ summary_*       │       │ notes           │  │
│ payment_method  │   │   │ created_at      │       └─────────────────┘  │
│ payment_freq    │   │   │ export_path     │                            │
│ amount_monthly  │   │   └─────────────────┘                            │
│ deleted_at      │   │                                                  │
│ referred_by_id  │───┤   ┌─────────────────┐       ┌─────────────────┐  │
│ commission_*    │   │   │ model_advances  │       │adhoc_payments   │  │
└─────────────────┘   │   ├─────────────────┤       ├─────────────────┤  │
        │             │   │ id (PK)         │       │ id (PK)         │  │
        │             │   │ model_id (FK)   │───────│ model_id (FK)   │──┘
        ▼             │   │ amount_total    │       │ pay_date        │
┌─────────────────┐   │   │ amount_remaining│       │ amount          │
│model_compensation   │   │ status          │       │ status          │
│  _adjustments   │   │   │ strategy        │       └─────────────────┘
├─────────────────┤   │   │ fixed_amount    │
│ id (PK)         │   │   │ percent_rate    │       ┌─────────────────┐
│ model_id (FK)   │───┘   └─────────────────┘       │login_attempts   │
│ effective_date  │               │                 ├─────────────────┤
│ amount_monthly  │               ▼                 │ id (PK)         │
│ notes           │       ┌─────────────────┐       │ username        │
└─────────────────┘       │advance_repayments       │ success         │
                          ├─────────────────┤       │ ip_address      │
                          │ id (PK)         │       │ attempted_at    │
                          │ advance_id (FK) │       └─────────────────┘
                          │ payout_id (FK)  │
                          │ amount          │       ┌─────────────────┐
                          │ source          │       │commission_payouts
                          └─────────────────┘       ├─────────────────┤
                                                    │ id (PK)         │
┌─────────────────┐       ┌─────────────────┐       │ referrer_id(FK) │
│validation_issues│       │model_referral_  │       │ referral_id(FK) │
├─────────────────┤       │    terms        │       │ pay_date        │
│ id (PK)         │       ├─────────────────┤       │ schedule_type   │
│ schedule_run_id │       │ id (PK)         │       │ amount          │
│ model_id (FK)   │       │ referrer_id(FK) │       │ status          │
│ severity        │       │ referral_id(FK) │       └─────────────────┘
│ issue           │       │ commission_*    │
└─────────────────┘       │ is_active       │
                          └─────────────────┘
```

### Table Details

#### `models` - Contractor/Performer Information

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment primary key |
| `status` | VARCHAR(20) | "Active" or "Inactive" |
| `code` | VARCHAR(50) | Unique identifier for the model |
| `real_name` | VARCHAR(200) | Legal name |
| `working_name` | VARCHAR(200) | Stage/working name |
| `start_date` | DATE | Employment start date |
| `payment_method` | VARCHAR(100) | e.g., "Paxum", "Wire", "Crypto" |
| `payment_frequency` | VARCHAR(20) | "weekly", "biweekly", "monthly" |
| `amount_monthly` | NUMERIC(12,2) | Monthly compensation |
| `crypto_wallet` | VARCHAR(200) | Crypto wallet address (optional) |
| `deleted_at` | DATETIME | Soft delete timestamp (null = active) |
| `referred_by_model_id` | INT (FK) | Self-reference for referral tracking |
| `commission_active` | BOOLEAN | Whether commission is active |
| `commission_per_referral` | NUMERIC(12,2) | Commission amount per referral |
| `commission_payout_frequency` | VARCHAR(20) | "monthly", "mid_month", "dual" |
| `commission_duration_months` | INT | How long commission lasts |
| `commission_status` | VARCHAR(20) | "paid" or "unpaid" |

**Constraints:**
- `ck_models_amount_positive`: `amount_monthly > 0`
- `ck_models_commission_status_valid`: `commission_status IN ('paid', 'unpaid')`

#### `schedule_runs` - Payroll Period Records

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment primary key |
| `target_year` | INT | Year of payroll period |
| `target_month` | INT | Month (1-12) of payroll period |
| `currency` | VARCHAR(10) | Currency code (default: "USD") |
| `include_inactive` | BOOLEAN | Whether inactive models were included |
| `summary_models_paid` | INT | Count of models in this run |
| `summary_total_payout` | NUMERIC(14,2) | Total payout amount |
| `summary_frequency_counts` | TEXT | JSON of frequency breakdown |
| `created_at` | DATETIME | When the run was created |
| `export_path` | VARCHAR(255) | Path to exported files |

#### `payouts` - Individual Payment Records

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment primary key |
| `schedule_run_id` | INT (FK) | Parent schedule run |
| `model_id` | INT (FK) | Associated model (nullable) |
| `pay_date` | DATE | Payment date |
| `code` | VARCHAR(50) | Model code (denormalized) |
| `real_name` | VARCHAR(200) | Real name snapshot |
| `working_name` | VARCHAR(200) | Working name snapshot |
| `payment_method` | VARCHAR(100) | Payment method snapshot |
| `payment_frequency` | VARCHAR(20) | Frequency snapshot |
| `amount` | NUMERIC(12,2) | Payment amount |
| `notes` | TEXT | Optional notes |
| `status` | VARCHAR(20) | "paid", "approved", "on_hold", "not_paid" |

**Indexes:**
- `idx_payout_run_status` (schedule_run_id, status)
- `idx_payout_run_model` (schedule_run_id, model_id)
- `ix_payouts_schedule_run_id` (schedule_run_id)
- `ix_payouts_model_id` (model_id)

#### `model_advances` - Cash Advance Tracking

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment primary key |
| `model_id` | INT (FK) | Model receiving the advance |
| `amount_total` | NUMERIC(12,2) | Original advance amount |
| `amount_remaining` | NUMERIC(12,2) | Amount still owed |
| `status` | VARCHAR(20) | "requested", "approved", "active", "closed" |
| `strategy` | VARCHAR(20) | "fixed" or "percent" deduction |
| `fixed_amount` | NUMERIC(12,2) | Fixed deduction per pay period |
| `percent_rate` | NUMERIC(5,2) | Percentage deduction (0-100) |
| `min_net_floor` | NUMERIC(12,2) | Minimum net pay after deduction |
| `max_per_run` | NUMERIC(12,2) | Maximum deduction per period |
| `cap_multiplier` | NUMERIC(5,2) | Multiplier for max deduction |
| `notes` | TEXT | Optional notes |
| `activated_at` | DATETIME | When advance became active |

**Workflow States:**
```
requested → approved → active → closed
```

---

## API Reference

### Router Overview

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth.py` | `/` | Login, logout, session management |
| `dashboard.py` | `/` | Dashboard views and exports |
| `models.py` | `/models` | Model CRUD, advances, adhoc payments |
| `schedules.py` | `/schedules` | Payroll runs, payouts, bulk updates |
| `commissions.py` | `/commissions` | Commission payout management |
| `admin.py` | `/admin` | User management, maintenance, diagnostics |
| `profile.py` | `/profile` | User profile, password change |
| `changelog.py` | `/` | Application changelog view |

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | Authenticate user |
| GET | `/logout` | End session |

### Dashboard Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Main dashboard with metrics (includes comprehensive payment totals) |
| GET | `/dashboard/export` | Export dashboard as CSV |
| GET | `/dashboard/export-xlsx` | Export dashboard as Excel |

#### Dashboard Metrics

The dashboard displays comprehensive payment totals that aggregate:
- **Payroll**: Regular scheduled payouts
- **Adhoc**: One-time payments outside schedules  
- **Commission**: Referral commission payouts

The "Top Earners" widget shows combined lifetime totals with breakdown.

### Model Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/models/` | List all models with comprehensive lifetime totals |
| GET | `/models/new` | New model form |
| POST | `/models/new` | Create model |
| GET | `/models/{id}` | Model detail view with payment breakdown |
| GET | `/models/{id}/edit` | Edit model form |
| POST | `/models/{id}/edit` | Update model |
| POST | `/models/{id}/delete` | Soft delete model |
| GET | `/models/payments` | All payments list |
| GET | `/models/export` | Export models CSV |
| POST | `/models/import` | Import models from CSV |

### Model Advance Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/models/{id}/advances` | Create advance request |
| POST | `/models/{id}/advances/{aid}/approve` | Approve advance |
| POST | `/models/{id}/advances/{aid}/repay` | Manual repayment |
| POST | `/models/{id}/advances/{aid}/delete` | Delete advance |
| POST | `/models/{id}/advances/{aid}/note` | Update advance notes |

### Model Adhoc Payment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/models/{id}/adhoc-payments` | Create adhoc payment |
| POST | `/models/{id}/adhoc-payments/{pid}/status` | Update status |
| POST | `/models/{id}/adhoc-payments/{pid}/notes` | Update notes |
| POST | `/models/{id}/adhoc-payments/{pid}/delete` | Delete payment |

### Schedule Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/schedules/` | List schedule runs |
| GET | `/schedules/new` | New schedule form |
| POST | `/schedules/new` | Create schedule run |
| GET | `/schedules/{run_id}` | Schedule detail with payouts |
| POST | `/schedules/{run_id}/delete` | Delete schedule run |
| POST | `/schedules/{run_id}/add-new-models` | Add new models to existing run (highlights new entries) |
| GET | `/schedules/{run_id}/download/{type}` | Download export file |
| POST | `/schedules/{run_id}/payouts/{pid}/status` | Update payout status |
| POST | `/schedules/{run_id}/payouts/{pid}/note` | Update payout notes |
| POST | `/schedules/{run_id}/payouts/bulk-update` | Bulk update payouts |
| POST | `/schedules/{run_id}/payouts/bulk-update/status` | Bulk status update |
| GET | `/schedules/all` | All payouts view |
| GET | `/schedules/all-table` | All payouts table view |
| GET | `/schedules/all-table/export` | Export all payouts |
| GET | `/schedules/adhoc` | Adhoc payments view |

### Commission Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/commissions/` | Commission dashboard |
| POST | `/commissions/{id}/status` | Update commission status |
| POST | `/commissions/{id}/delete` | Delete commission payout |

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | User management list |
| GET | `/admin/users/new` | New user form |
| POST | `/admin/users/new` | Create user |
| GET | `/admin/users/{id}/edit` | Edit user form |
| POST | `/admin/users/{id}/edit` | Update user |
| POST | `/admin/users/{id}/reset-password` | Reset user password |
| POST | `/admin/users/{id}/unlock` | Unlock user account |
| POST | `/admin/users/{id}/delete` | Delete user |
| GET | `/admin/models/{id}/purge` | Purge model confirmation |
| POST | `/admin/models/{id}/purge` | Hard delete model |
| GET | `/admin/settings` | Admin settings page |
| POST | `/admin/maintenance/cleanup-empty-runs` | Remove empty schedule runs |
| POST | `/admin/maintenance/cleanup-orphans` | Remove orphaned records |
| POST | `/admin/maintenance/reset-application-data` | Reset all data |
| GET | `/admin/diagnostics/db` | Database diagnostics |

### Health Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/db` | Database health with timing |

---

## Authentication & Security

### Session Management

Sessions are managed via HTTP cookies with the following flow:

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
│ Browser │────▶│  Login  │────▶│ Validate │────▶│  Create  │
│         │     │  Form   │     │ Password │     │ Session  │
└─────────┘     └─────────┘     └──────────┘     └──────────┘
                                     │                 │
                                     ▼                 ▼
                              ┌──────────┐     ┌──────────┐
                              │ Record   │     │ Set      │
                              │ Attempt  │     │ Cookie   │
                              └──────────┘     └──────────┘
```

### Rate Limiting & Account Lockout

**Configuration:**
```python
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW_MINUTES = 15
```

**Lockout Flow:**
1. User fails login attempt
2. `failed_login_count` increments
3. Attempt recorded in `login_attempts` table
4. After 5 failures in 15 minutes:
   - `is_locked = True`
   - `locked_until = now + 15 minutes`
5. Auto-unlock after period expires

### Password Hashing

- Algorithm: bcrypt with salt
- Location: `app/auth.py::User.hash_password()`
- Verification: `app/auth.py::User.verify_password()`

### Role-Based Access

| Role | Permissions |
|------|-------------|
| `user` | View dashboard, models, schedules |
| `admin` | All user permissions + admin panel |

### Middleware

| Middleware | Location | Purpose |
|------------|----------|---------|
| `CacheControlMiddleware` | `app/main.py` | Static asset cache headers |

**Cache-Control Policies:**
```
Hashed files (*.js, *.css with hash):  Cache-Control: public, max-age=31536000, immutable
Non-hashed files:                      Cache-Control: public, max-age=86400, must-revalidate
```

---

## Core Business Logic

### Payroll Calculation

Location: `app/core/payroll.py`

#### Payment Frequency Logic

```python
FREQUENCY_PLANS = {
    "weekly": [0, 1, 2, 3],    # All 4 weeks
    "biweekly": [1, 3],        # 2nd and 4th weeks
    "monthly": [3],            # Last week only
}
```

Pay dates are calculated based on the week of the month (0-indexed):
- Week 0: 1st-7th
- Week 1: 8th-14th
- Week 2: 15th-21st
- Week 3: 22nd-end

#### Amount Calculation

```
Weekly:    amount_per_pay = amount_monthly / 4
Biweekly:  amount_per_pay = amount_monthly / 2
Monthly:   amount_per_pay = amount_monthly
```

### Compensation Adjustments

Models can have scheduled compensation changes:

```python
class ModelCompensationAdjustment:
    model_id: int
    effective_date: date
    amount_monthly: Decimal
    notes: str
```

When generating payroll:
1. Find adjustment with `effective_date <= pay_date`
2. Use that adjustment's `amount_monthly`
3. Fall back to model's base `amount_monthly`

### Cash Advance Deductions

#### Deduction Strategies

| Strategy | Calculation |
|----------|-------------|
| `fixed` | Deduct `fixed_amount` per pay period |
| `percent` | Deduct `percent_rate`% of gross pay |

#### Guardrails

| Guardrail | Description |
|-----------|-------------|
| `min_net_floor` | Never reduce net pay below this amount |
| `max_per_run` | Maximum deduction per pay period |
| `cap_multiplier` | Scale factor for maximum deduction |

#### Deduction Flow

```
1. Calculate gross pay from schedule
2. For each active advance:
   a. Calculate deduction based on strategy
   b. Apply cap_multiplier
   c. Ensure net >= min_net_floor
   d. Ensure deduction <= max_per_run
   e. Ensure deduction <= amount_remaining
3. Record deduction in advance_repayments
4. Update amount_remaining
5. If amount_remaining == 0: status = "closed"
```

### Commission System

#### Referral Terms

Each referral relationship has configurable terms:

```python
class ModelReferralTerm:
    referrer_model_id: int      # Who referred
    referral_model_id: int      # Who was referred
    commission_per_referral: Decimal
    commission_payout_frequency: str  # "monthly", "mid_month", "dual"
    commission_duration_months: int   # How long to pay
    is_active: bool
```

#### Payout Frequency

| Frequency | Pay Dates |
|-----------|-----------|
| `monthly` | End of month |
| `mid_month` | 15th of month |
| `dual` | Both 15th and end of month |

### Soft Delete

Models support soft deletion to preserve historical data:

```python
# Soft delete
model.deleted_at = datetime.now()
db.commit()

# Query active models only
stmt = select(Model).where(Model.deleted_at.is_(None))

# Hard delete (admin only)
db.delete(model)
db.commit()
```

---

## Data Flow Diagrams

### Create Schedule Run

```
┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌───────────┐
│  Form    │──▶│  Validate  │──▶│ Create Run  │──▶│  Load     │
│  Submit  │   │  Inputs    │   │  Record     │   │  Models   │
└──────────┘   └────────────┘   └─────────────┘   └─────┬─────┘
                                                        │
     ┌──────────────────────────────────────────────────┘
     ▼
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│  Generate  │──▶│  Create    │──▶│  Apply     │──▶│  Store     │
│  Schedule  │   │  Payouts   │   │  Advances  │   │  Results   │
└────────────┘   └────────────┘   └────────────┘   └────────────┘
                                                        │
     ┌──────────────────────────────────────────────────┘
     ▼
┌────────────┐   ┌────────────┐
│  Export    │──▶│  Redirect  │
│  Files     │   │  to Detail │
└────────────┘   └────────────┘
```

### Update Payout Status

```
┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌───────────┐
│  Status  │──▶│  Validate  │──▶│ Update DB   │──▶│ Invalidate│
│  Change  │   │  Status    │   │  Record     │   │  Cache    │
└──────────┘   └────────────┘   └─────────────┘   └───────────┘
```

### Cash Advance Lifecycle

```
┌──────────────┐
│   REQUESTED  │◄─── Model submits advance request
└──────┬───────┘
       │ Admin approves
       ▼
┌──────────────┐
│   APPROVED   │◄─── Ready for activation
└──────┬───────┘
       │ First deduction occurs
       ▼
┌──────────────┐
│    ACTIVE    │◄─── Deductions happening each pay period
└──────┬───────┘
       │ amount_remaining reaches 0
       ▼
┌──────────────┐
│    CLOSED    │◄─── Fully repaid
└──────────────┘
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYROLL_DATABASE_URL` | `postgresql://payroll:payroll@localhost:5432/payroll_dev` | Database connection URL |
| `ENVIRONMENT` | - | Set to "development" for dev mode |
| `LOCAL_DEV_SQLITE_FALLBACK` | `false` | Allow SQLite fallback in dev |
| `LOG_QUERIES` | `false` | Enable query timing logs |
| `DB_POOL_SIZE` | `5` | PostgreSQL pool size |
| `DB_MAX_OVERFLOW` | `10` | PostgreSQL max overflow |
| `DB_POOL_RECYCLE` | `3600` | Connection recycle time (seconds) |
| `DB_CONNECT_RETRIES` | `3` | Connection retry attempts |
| `DB_RETRY_DELAY` | `1.0` | Initial retry delay (seconds) |

### Database URLs

**PostgreSQL (Production):**
```
postgresql://user:password@host:5432/payroll_db
```

**SQLite (Development):**
```
sqlite:///data/payroll.db
```

---

## File Structure

```
PayrollDesk/
├── app/
│   ├── __init__.py          # Version definition
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic validation schemas
│   ├── crud.py              # Database operations (2034 lines)
│   ├── database.py          # Database configuration
│   ├── auth.py              # User model, password hashing
│   ├── security.py          # Rate limiting, lockout logic
│   ├── services.py          # Business service layer
│   ├── dependencies.py      # FastAPI dependencies
│   ├── commission.py        # Commission calculations
│   ├── core/
│   │   ├── payroll.py       # Core payroll logic
│   │   └── formatting.py    # Display formatters
│   ├── routers/
│   │   ├── auth.py          # Login/logout routes
│   │   ├── dashboard.py     # Dashboard routes
│   │   ├── models.py        # Model CRUD routes
│   │   ├── schedules.py     # Schedule routes
│   │   ├── commissions.py   # Commission routes
│   │   ├── admin.py         # Admin routes
│   │   ├── profile.py       # Profile routes
│   │   └── changelog.py     # Changelog route
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS, JS, images
│   ├── exporting/           # Export utilities
│   └── importers/           # CSV/Excel importers
├── migrations/
│   ├── versions/            # Alembic migration files
│   └── env.py               # Alembic environment
├── tests/                   # Test suite (194 tests)
├── docs/                    # Documentation
├── exports/                 # Generated export files
├── data/                    # SQLite database (dev)
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container configuration
├── CHANGELOG.md             # Version history
├── README.md                # Project overview
└── TODO.md                  # Task tracking
```

### Key File Sizes

| File | Lines | Coverage |
|------|-------|----------|
| `app/crud.py` | 2,034 | 86% |
| `app/core/payroll.py` | 531 | - |
| `app/models.py` | 397 | - |
| `app/services.py` | 261 | - |
| `app/database.py` | 254 | - |
| `app/schemas.py` | 204 | - |
| `app/security.py` | 169 | - |

---

## Appendix

### Status Enumerations

```python
STATUS_ENUM = ("Active", "Inactive")
FREQUENCY_ENUM = ("weekly", "biweekly", "monthly")
PAYOUT_STATUS_ENUM = ("paid", "approved", "on_hold", "not_paid")
ADHOC_PAYMENT_STATUS_ENUM = ("pending", "paid", "cancelled")
COMMISSION_PAYOUT_FREQUENCY_ENUM = ("monthly", "mid_month", "dual")
COMMISSION_STATUS_ENUM = ("unpaid", "paid")
```

### Database Migrations

| Revision | Description |
|----------|-------------|
| `0001` | Initial baseline |
| `e50dc541277e` | Add `deleted_at` column to models |
| `f61db652388a` | Add payout composite indexes |

### Test Coverage Summary

- **Total Tests:** 194
- **CRUD Coverage:** 86%
- **Key Test Files:**
  - `test_crud_models.py` (20 tests)
  - `test_crud_payouts.py` (18 tests)
  - `test_crud_referrals.py` (15 tests)
  - `test_crud_advances.py` (17 tests)
  - `test_crud_adhoc.py` (10 tests)
  - `test_integration_workflows.py` (14 tests)
  - `test_error_scenarios.py` (20 tests)

---

*Document generated for PayrollDesk v2.32.2*
