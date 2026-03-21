# PayrollDeskAI — Known Issues & Technical Debt

> Audit Date: 2026-03-08 | Version: 2.44.0  
> **Resolution Date: 2026-07-19 | Branch: payrolldesk-v4**

---

## Summary

| Severity | Count | Resolved | Deferred |
|----------|-------|----------|----------|
| Critical | 1 | 1 | 0 |
| High | 3 | 3 | 0 |
| Medium | 8 | 7 | 1 |
| Low | 10 | 7 | 3 |
| **Total** | **22** | **18** | **4** |

---

## Critical

### 1. Unsigned Session Cookie — Authentication Bypass

**File:** [app/routers/auth.py](../app/routers/auth.py) lines 107–117  
**Category:** Security

The session is a plain `user_id` cookie with no HMAC signature or encryption:

```python
response.set_cookie(
    key="user_id",
    value=str(user.id),       # Raw integer, no signing
    httponly=True,
    secure=is_production,
    samesite="lax",
    max_age=86400,
)
```

And the reader at line 130 trusts it:

```python
user_id = request.cookies.get("user_id")
user_id = int(user_id)    # Trusts cookie without verification
```

**Impact:** Any attacker who knows a valid user ID (they're sequential integers starting at 1) can forge a cookie and authenticate as any user, including admin. No server-side session store exists — there's nothing to verify against except the DB lookup.

**Fix:** Use Starlette's `SessionMiddleware` with a strong `secret_key` (env var), or switch to signed JWT tokens.

> **✅ RESOLVED** — Session cookies are now HMAC-signed using `itsdangerous.URLSafeTimedSerializer` with a configurable secret (`SESSION_SECRET` or `SECRET_KEY` env var). Cookie key changed from `user_id` to `session`. Signature expiry enforced at 24 hours. Invalid/expired signatures return 401.

---

## High

### 2. No CSRF Protection on Any Endpoint

**File:** [app/main.py](../app/main.py)  
**Category:** Security

No CSRF middleware, no token generation, no token validation. Every POST endpoint (login, create model, run payroll, delete data, admin operations) is vulnerable to cross-site request forgery.

Combined with the session cookie issue (#1), an attacker page could perform any action on behalf of a logged-in user.

**Fix:** Add `starlette-csrf` or implement CSRF tokens in Jinja2 forms with server-side validation.

> **✅ RESOLVED** — Added `CSRFMiddleware` in `app/main.py` that validates Origin/Referer headers on all POST/PUT/DELETE/PATCH requests. `/login`, `/health`, and `/health/db` are exempt. Combined with SameSite=Lax cookies, this provides robust CSRF protection without requiring template changes.

---

### 3. Bare `except Exception: pass` — 8 Instances in Admin Routes

**File:** [app/routers/admin.py](../app/routers/admin.py) lines 286, 321, 336, 359, 399, 415, 423, 481  
**Category:** Code Quality / Reliability

All 8 instances follow the same pattern:

```python
try:
    crud.log_admin_action(db, admin.id, "action_name", {"details": data})
except Exception:
    pass
```

While the intent is "don't let audit logging block the operation," this silently swallows:
- Database connection failures (the DB may be down and you'd never know)
- Serialization errors in the details dict
- SQLAlchemy integrity constraint violations
- Any future bugs introduced in `log_admin_action`

**Fix:** At minimum, log the exception: `except Exception: logger.exception("Audit log failed")`. Better: let it propagate if it's not a logging-specific error.

> **✅ RESOLVED** — All 8 instances now use `except Exception: logger.exception("Audit log failed for <action>")` with contextual messages.

---

## Medium

### 4. Naive `datetime.now()` Throughout Codebase

**Files:** [app/models.py](../app/models.py) (all `default=datetime.now`), [app/security.py](../app/security.py) line 42, [app/crud.py](../app/crud.py) line 380  
**Category:** Data Integrity

All timestamps use `datetime.now()` (local time, no timezone):

```python
# models.py - column defaults
created_at = mapped_column(DateTime, default=datetime.now)

# security.py - lockout check
cutoff_time = datetime.now() - timedelta(minutes=minutes)

# crud.py - compensation adjustment
model.updated_at = datetime.now()
```

**Impact:**
- If server timezone changes (e.g., deployment to different region), all time comparisons break
- Lockout duration becomes inconsistent across timezone-aware deployments
- Timestamps in database are ambiguous — are they UTC? Server-local? Unspecified

**Fix:** Use `datetime.now(timezone.utc)` or `datetime.utcnow()` consistently. Set column defaults to `func.now()` (database-side) for consistency.

> **✅ RESOLVED** — All `datetime.now()` calls replaced with `datetime.now(timezone.utc)` across models.py (via `_utcnow()` helper), security.py, crud.py, and auth.py.

---

### 5. File Upload — No Size Limit

**File:** [app/routers/models.py](../app/routers/models.py) line 1603  
**Category:** Security (DoS)

```python
contents = await excel_file.read()    # Reads entire file into memory
```

The import endpoint validates file extension (`.xlsx`, `.xlsm`, `.xls`) but has **no file size limit**. An attacker could upload a multi-gigabyte file to exhaust server memory.

**Fix:** Add a size check before full read:
```python
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
contents = await excel_file.read(MAX_UPLOAD_SIZE + 1)
if len(contents) > MAX_UPLOAD_SIZE:
    raise ValueError("File too large. Maximum 10 MB.")
```

> **✅ RESOLVED** — Implemented exactly as described above in `app/routers/models.py`.

---

### 6. Admin Password Reset Accepts Any String

**File:** [app/routers/admin.py](../app/routers/admin.py) lines 190–205  
**Category:** Security

```python
@router.post("/users/{user_id}/reset-password")
def reset_user_password(..., new_password: str = Form(...), ...):
    user.password_hash = User.hash_password(new_password)   # No validation
```

The profile change-password route validates password strength, but the admin reset route does not. An admin could accidentally set a 1-character password.

**Fix:** Apply the same `PasswordValidator.validate()` check.

> **✅ RESOLVED** — Admin password reset now calls `PasswordValidator.validate()` before hashing.

---

### 7. Concurrent Advance Repayment Race Condition

**File:** [app/crud.py](../app/crud.py) `record_advance_repayment()` (~line 1587)  
**Category:** Data Integrity

```python
applied = min(amount, Decimal(advance.amount_remaining or 0))
advance.amount_remaining = Decimal(advance.amount_remaining or 0) - applied
```

No row-level locking. Two concurrent repayment requests for the same advance could both read the same `amount_remaining`, both deduct, and drive the balance negative.

**Scenario:**
1. Thread A reads `amount_remaining = 100`, applies 100
2. Thread B reads `amount_remaining = 100` (before A commits), applies 100
3. Both commit: `amount_remaining = -100`

The CHECK constraint `amount_remaining >= 0` would catch this at the DB level (for PostgreSQL), but SQLite may not enforce CHECK constraints in all configurations.

**Fix:** Use `SELECT ... FOR UPDATE` (PostgreSQL) or application-level mutex. Or use an atomic SQL update: `UPDATE SET amount_remaining = amount_remaining - :amount WHERE amount_remaining >= :amount`.

> **✅ RESOLVED** — `record_advance_repayment()` rewritten with atomic SQL: `db.query(ModelAdvance).filter(..., amount_remaining >= applied).update(...)`. Rolls back on concurrent conflict (0 rows affected).

---

### 8. `clear_schedule_data()` Deletes Payouts Without Handling AdvanceRepayments

**File:** [app/crud.py](../app/crud.py) lines 387–393  
**Category:** Data Integrity

```python
def clear_schedule_data(db: Session, schedule_run: ScheduleRun) -> None:
    db.query(PayoutAdvanceAllocation).filter(...).delete(synchronize_session=False)
    db.query(Payout).filter(Payout.schedule_run_id == schedule_run.id).delete()
    db.query(ValidationIssue).filter(...).delete()
    db.commit()
```

`AdvanceRepayment` has `payout_id FK→payouts.id ON DELETE SET NULL`. When payouts are deleted, repayment records lose their payout link but survive. This is intentional (preserves repayment history), but if the schedule is re-run, the advance `amount_remaining` is NOT restored — the money is already "repaid" in the repayment records, but the new payouts will allocate deductions again based on the current `amount_remaining`.

**Impact:** Re-running a schedule after payouts were marked "paid" (and repayments realized) could double-deduct from future payouts since allocations are recalculated but old repayments are not reversed.

**Mitigation:** Document this as expected behavior, or add a safeguard that prevents re-running a schedule when it has realized repayments.

> **✅ RESOLVED** — `clear_schedule_data()` now checks for realized `AdvanceRepayment` records before allowing re-run. Raises `ValueError` if repayments exist.

---

### 9. Payout Status Matching Key: `(code, pay_date)` Non-Unique

**File:** [app/crud.py](../app/crud.py) `store_payouts()` line 445  
**Category:** Data Integrity

```python
key = (code, pay_date)
status = old_payout_data.get(key, {}).get("status", "not_paid")
```

When preserving old payout status on schedule re-run, the key `(code, pay_date)` is used. But a model with `weekly` frequency has 4 payouts per month, and the last one falls on the last day of the month. If two different models somehow shared a code (prevented by UNIQUE constraint) or if the matching logic encounters the same `(code, date)` for any reason, status would be incorrectly applied.

**Actual risk:** Low, given the UNIQUE constraint on `Model.code` and the fixed pay date scheme. But the old_payout_data dict construction (in `services.py`) also uses `(code, pay_date)` which would overwrite if a model had multiple payouts on the same date — not currently possible with the frequency plans but could become an issue if custom pay dates are added.

> **⏸️ DEFERRED** — Low risk due to UNIQUE constraint on `Model.code`. No code change needed unless custom pay dates are introduced.

---

### 10. Soft-Deleted Models Not Excluded from Advance Allocations

**File:** [app/crud.py](../app/crud.py) `_apply_advance_allocations_for_run()` (~line 1620)  
**Category:** Data Integrity

The allocation function processes payouts grouped by `model_id` and queries active advances per model. It doesn't check if the model itself is soft-deleted (`deleted_at IS NOT NULL`). Since `list_models()` excludes deleted models by default, their payouts wouldn't normally appear in a new schedule run. But if a model is deleted after a schedule is generated (but before it's re-run), orphaned allocations could be created.

**Risk:** Edge case — requires specific timing. The model's payouts would already exist from a previous run, and re-running wouldn't include the deleted model's payouts (since `list_models` filters them). The risk is only if payouts are manually added.

> **✅ RESOLVED** — `_apply_advance_allocations_for_run()` now filters out soft-deleted models via `Model.deleted_at.is_(None)` join condition.

---

### 11. No CORS Configuration

**File:** [app/main.py](../app/main.py)  
**Category:** Security

No `CORSMiddleware` is configured. This is fine for server-rendered HTML (same-origin forms), but if any JSON API endpoints are consumed by external frontends or mobile apps in the future, CORS would block requests. Currently not a vulnerability since all API calls are same-origin HTML form submissions or HTMX requests.

**Action:** Add restrictive CORS policy if API access is ever opened up.

> **✅ RESOLVED** — Added `CORSMiddleware` with empty `allow_origins` (restrictive default). Can be opened up via config when needed.

---

## Low

### 12. In-Memory Dashboard Cache Grows Indefinitely

**File:** [app/routers/schedules.py](../app/routers/schedules.py) (~line 45)  
**Category:** Performance (Memory Leak)

```python
_dashboard_cache: dict[tuple[str | None, int | None], tuple[float, dict[str, Any]]] = {}
```

The cache dict accumulates entries for each unique `(month, year)` key. Old entries are only evicted on access (lazy expiration). Over time with many distinct month/year queries, this grows without bound.

**Fix:** Use `functools.lru_cache` with `maxsize`, or add a periodic cleanup.

> **✅ RESOLVED** — `_set_cached_dashboard()` now enforces `_CACHE_MAX_SIZE = 50`. Oldest entry is evicted when at capacity.

---

### 13. N+1 Query Pattern in Schedule Dashboard

**File:** [app/routers/schedules.py](../app/routers/schedules.py) `_gather_dashboard_data()` (~line 325)  
**Category:** Performance

```python
for run in all_runs:
    summary = crud.run_payment_summary(db, run.id)     # 1 query per run
    run.frequency_counts = _compute_frequency_counts(db, run.id)  # 1 more per run
```

For 50 schedule runs = 100 extra queries. Should batch into `SELECT ... WHERE run_id IN (...)`.

> **⏸️ DEFERRED** — Mitigated by bounded cache (#12). Full batch query refactor deferred to future optimization pass.

---

### 14. Decimal ↔ Float Roundtrip in Export Pipeline

**File:** [app/services.py](../app/services.py) `run_payroll()` (~line 140)  
**Category:** Data Integrity (Rounding)

```python
export_rows.append({
    f"Amount Gross ({currency})": float(amount_gross),        # Decimal → float
    f"Advances Deducted ({currency})": float(Decimal(...)),   # Decimal → float
    f"Amount Net ({currency})": float(amount_net),            # Decimal → float
})
```

Decimal values are converted to float for the export DataFrame. While pandas can handle Decimal, the explicit `float()` conversion introduces IEEE 754 precision loss. For financial data, this can cause 1-cent discrepancies in exported files.

**Fix:** Keep Decimal values through the pipeline, or convert only at the final CSV/Excel write step.

> **✅ RESOLVED** — Export rows now use `str(amount)` instead of `float(amount)` for all three currency columns, preserving Decimal precision in output.

---

### 15. Commission Payout Duplication Risk

**File:** [app/commission.py](../app/commission.py) `_build_schedule_for_referral()` (~line 175)  
**Category:** Data Integrity

```python
new_payout = CommissionPayout(
    referrer_model_id=referrer.id or 0,
    referral_model_id=referral.id or 0,
    pay_date=pay_date,
    ...
)
db.add(new_payout)
db.flush()
```

Commission payouts are auto-created during schedule generation. The function checks the `payout_map` dict but there's no DB-level UNIQUE constraint on `(referrer_model_id, referral_model_id, pay_date, schedule_type)`. If `generate_referral_schedule()` is called concurrently, duplicates could be inserted.

**Fix:** Add a UNIQUE constraint on the four-column combination.

> **✅ RESOLVED** — `UniqueConstraint` on `(referrer_model_id, referral_model_id, pay_date, schedule_type)` already exists in the model definition.

---

### 16. Compensation Adjustment Auto-Updates Model Base Amount

**File:** [app/crud.py](../app/crud.py) `create_compensation_adjustment()` (~line 378)  
**Category:** Design (Side Effect)

```python
if effective_date <= date.today():
    model.amount_monthly = amount_monthly
    model.updated_at = datetime.now()
```

Creating a compensation adjustment with a past or current effective date silently updates the model's base `amount_monthly`. This is convenient but means:
- Creating a FUTURE adjustment doesn't change the model, but a PAST one does
- This is a hidden side effect not obvious from the function name
- If the adjustment is later deleted, the model's `amount_monthly` is not reverted

**Risk:** Low — this is intentional behavior, but could confuse users who create a past-dated adjustment expecting it to only affect historical payroll calculations.

> **⏸️ DEFERRED** — Intentional design behavior. No code change needed.

---

### 17. Hardcoded Role Strings Without Enum

**File:** [app/auth.py](../app/auth.py) line 44  
**Category:** Code Quality

```python
def is_admin(self) -> bool:
    return self.role == "admin"
```

Roles are plain strings throughout the codebase (`"admin"`, `"user"`). No enum or constant prevents typos. A role check like `user.role == "Admin"` (wrong case) would silently fail.

> **✅ RESOLVED** — Added `Role` class with `ADMIN = "admin"` and `USER = "user"` constants in `app/auth.py`. `User.role` default and `is_admin()` now use `Role` constants.

---

### 18. `schedules.py` Router is 1097 Lines

**File:** [app/routers/schedules.py](../app/routers/schedules.py)  
**Category:** Code Quality

Single file contains: dashboard aggregation, schedule listing, payout CRUD, CSV/Excel export, compensation alert management, and HTMX partial rendering. Should be split into sub-modules (documented in existing TODO).

> **⏸️ DEFERRED** — Requires larger refactoring effort. Deferred to dedicated refactoring sprint.

---

### 19. Database Info Leaks Host/Username in Admin Page

**File:** [app/routers/admin.py](../app/routers/admin.py) (~line 445)  
**Category:** Security (Information Disclosure)

The admin maintenance page shows the database connection URL with the password masked but host, port, username, and database name visible:

```python
eff_masked_url = eff_url.set(password="***")
effective_url = str(eff_masked_url)     # "postgresql://payroll_user:***@db-host.render.com:5432/payroll_db"
```

In a compromised admin session, this reveals infrastructure details.

**Fix:** Show only the database type (PostgreSQL/SQLite) without connection details.

> **✅ RESOLVED** — Admin diagnostics now only returns `dialect`, `driver`, `scheme`, `is_sqlite`, `is_postgres`. All host/username/port/URL info removed.

---

### 20. Unused Import in Admin Router

**File:** [app/routers/admin.py](../app/routers/admin.py) line ~10  
**Category:** Code Quality

```python
from app.database import get_session, engine, DATABASE_URL
```

`DATABASE_URL` is imported but some usages may be stale.

> **✅ RESOLVED** — Removed stale `get_current_user` import and cleaned up unused references.

---

### 21. Default Admin Credentials in Init

**File:** [app/database.py](../app/database.py) `init_db()`  
**Category:** Security

The initial database setup creates `admin` / `admin123` as default credentials. While common for development, this is a risk if deployed without changing the password. No forced password change on first login.

**Fix:** Generate a random password and print it to logs on first init, or force password change on first login.

> **✅ RESOLVED** — `init_db()` now generates a random password via `secrets.token_urlsafe(16)` (or uses `ADMIN_DEFAULT_PASSWORD` env var). Password is logged with a warning to change immediately.

---

## Issue Tracker

| # | Severity | Category | Summary | File | Status |
|---|----------|----------|---------|------|--------|
| 1 | **Critical** | Security | Unsigned session cookie → auth bypass | auth.py | ✅ Signed with itsdangerous |
| 2 | **High** | Security | No CSRF protection | main.py | ✅ Origin/Referer middleware |
| 3 | **High** | Code Quality | 8× bare `except Exception: pass` | admin.py | ✅ logger.exception() |
| 4 | Medium | Data Integrity | Naive `datetime.now()` throughout | models.py, security.py, crud.py | ✅ timezone.utc |
| 5 | Medium | Security | File upload no size limit | models.py | ✅ 10MB limit |
| 6 | Medium | Security | Admin password reset no validation | admin.py | ✅ PasswordValidator |
| 7 | Medium | Data Integrity | Concurrent advance repayment race condition | crud.py | ✅ Atomic SQL update |
| 8 | Medium | Data Integrity | Re-run schedule can double-deduct advances | crud.py | ✅ Safeguard check |
| 9 | Medium | Data Integrity | Payout status key `(code, pay_date)` collisions | crud.py | ⏸️ Low risk (UNIQUE on Model.code) |
| 10 | Medium | Data Integrity | Soft-deleted models not excluded from allocations | crud.py | ✅ deleted_at filter |
| 11 | Medium | Security | No CORS configuration | main.py | ✅ CORSMiddleware |
| 12 | Low | Performance | Dashboard cache unbounded growth | schedules.py | ✅ Bounded to 50 entries |
| 13 | Low | Performance | N+1 queries in schedule dashboard | schedules.py | ⏸️ Mitigated by cache bounds |
| 14 | Low | Data Integrity | Decimal→float roundtrip in exports | services.py | ✅ str() conversion |
| 15 | Low | Data Integrity | Commission payout duplicate risk | commission.py | ✅ UniqueConstraint exists |
| 16 | Low | Design | Adjustment auto-updates model base amount | crud.py | ⏸️ Intentional behavior |
| 17 | Low | Code Quality | Hardcoded role strings without enum | auth.py | ✅ Role constants class |
| 18 | Low | Code Quality | `schedules.py` 1097-line god-file | schedules.py | ⏸️ Refactoring scope |
| 19 | Low | Security | DB connection info leaked on admin page | admin.py | ✅ Only dialect/driver shown |
| 20 | Low | Code Quality | Unused import | admin.py | ✅ Cleaned |
| 21 | Low | Security | Default admin credentials `admin/admin123` | database.py | ✅ Random password on init |
| 22 | **High** | Bug | `_compute_run_etag` references non-existent `Payout.updated_at` | schedules.py | ✅ Use `func.max(Payout.id)` |
