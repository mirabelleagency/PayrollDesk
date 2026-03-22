> **ARCHIVED** — All 29 enhancements completed as of v2.48.1.
> See [CHANGELOG.md](../../CHANGELOG.md) for release history.

# PayrollDesk Enhancement Plan

> Generated from system flow analysis on payrolldesk-v4 branch.

---

## Current System Strengths

- **ACID advance deductions**: Atomic SQL-level updates prevent race conditions
- **Two-phase advance workflow**: Allocate (planning) → Realize (on "paid") prevents premature deductions
- **Idempotent re-runs**: Payout status/notes preserved on schedule refresh
- **Frequency math**: Rounding adjustment on last payout handles edge cases correctly
- **Compensation adjustments**: Properly pro-rated for mid-period rate changes

---

## Enhancement Tracker

| #  | Enhancement                          | Priority | Effort   | Status      | Notes |
|----|--------------------------------------|----------|----------|-------------|-------|
| 1  | Transaction safety wrapper           | 🔴 HIGH  | 1 hour   | ✅ Done     | Delivered in Schedule Revamp Phase 6 |
| 2  | Background payroll processing        | 🔴 HIGH  | 3-5 days | ✅ Done     | Delivered in Schedule Revamp Phase 10 |
| 3  | Auto-resolve compensation alerts     | 🔴 HIGH  | 2 days   | ✅ Done     | Delivered in Schedule Revamp Phase 9 |
| 4  | Batch N+1 query optimization         | 🟠 MED   | 1-2 days | ✅ Done     | batch_run_payment_summaries + batch_frequency_counts in crud.py |
| 5  | Re-run safeguard (paid payouts)      | 🟠 MED   | 1-2 days | ✅ Done     | Delivered in Schedule Revamp Phase 3 (selective refresh + payout locking) |
| 6  | Advance deduction confirmation       | 🟠 MED   | 1 day    | ✅ Done     | Confirm dialog when marking payout as paid with active advance |
| 7  | Exclude "approved" from overdue      | 🟢 LOW   | 30 min   | ✅ Done     | Already excluded — overdue only counts not_paid/on_hold |
| 8  | Advance deduction toast on paid      | 🟢 LOW   | 2 hours  | ✅ Done     | showAdvanceToast() on single + bulk status updates |
| 9  | Bulk compensation alert resolution   | 🟢 LOW   | 3 hours  | ✅ Done     | Already implemented — Apply All Pro-rated + Dismiss All buttons |
| 10 | Bulk advance approval workflow       | 🟢 LOW   | 1 day    | ✅ Done     | /admin/advances/pending page with checkbox bulk approve |
| 11 | Export cache with ETag               | 🟢 LOW   | 1 day    | ✅ Done     | Lightweight data-timestamp ETag + 304 Not Modified on exports |
| 12 | Unify admin user management styling  | 🟠 MED   | 2-3 hrs  | ✅ Done     | users.html + user_form.html rewritten with design system classes |
| 13 | Admin audit log viewer               | 🟠 MED   | 3-4 hrs  | ✅ Done     | New /admin/audit-log page with pagination and filtering |
| 14 | CSRF protection on admin forms       | 🔴 HIGH  | 2-3 hrs  | ✅ Done     | HMAC token-based CSRF on all POST forms |
| 15 | Pay config UX improvements           | 🟢 LOW   | 3-4 hrs  | ✅ Done     | Visual day picker toggle buttons synced with JSON input |
| 16 | Password reset UX improvements       | 🟢 LOW   | 1-2 hrs  | ✅ Done     | Dialog modal with new password + confirm + mismatch validation |
| 17 | Frequency plan computed dates preview | 🟢 LOW   | 1-2 hrs  | ✅ Done     | Resolved Pay Dates column with ordinal day labels |
| 18 | Password reset should auto-unlock    | 🔴 HIGH  | 15 min   | ✅ Done     | Already implemented in admin.py reset-password handler |
| 19 | Unauth export route protection       | 🔴 HIGH  | 30 min   | ✅ Done     | All export routes already have `get_current_user` dependency |
| 20 | Payout duplicate prevention          | 🟠 MED   | 1 hr     | ✅ Done     | UniqueConstraint already on (schedule_run_id, model_id, pay_date) |
| 21 | Soft-delete filter enforcement       | 🟠 MED   | 2-3 hrs  | ✅ Done     | `get_model()` already filters `deleted_at IS NULL` by default |
| 22 | Division by zero guard in dashboard  | 🔴 HIGH  | 15 min   | ✅ Done     | `if active_count:` guard already in models.py |
| 23 | Import error display in UI           | 🟠 MED   | 1-2 hrs  | ✅ Done     | Errors shown in collapsible details section; now includes adjustment/adhoc errors |
| 24 | Excel importer sheet name validation | 🟢 LOW   | 30 min   | ✅ Done     | Error now lists available sheet names |
| 25 | Populate gross_amount on payouts     | 🟠 MED   | 1-2 hrs  | ✅ Done     | Already set at payout creation in crud.py |
| 26 | Commission payouts in XLSX export    | 🟢 LOW   | 1-2 hrs  | ✅ Done     | CommissionPayouts sheet added to XLSX export |
| 27 | Empty state messages for lists       | 🟢 LOW   | 1 hr     | ✅ Done     | Both models and schedules list pages have empty state cards |
| 28 | Session secret production guard      | 🔴 HIGH  | 15 min   | ✅ Done     | RuntimeError raised in auth.py if no secret set in production |
| 29 | Update docs for PostgreSQL-only      | 🟢 LOW   | 30 min   | ✅ Done     | ALEMBIC_GUIDE, SYSTEM_OVERVIEW, TECHNICAL_SPEC updated |

> **Schedule Revamp** — All 10 phases completed. See [SCHEDULE_REVAMP.md](SCHEDULE_REVAMP.md) for full details, phase breakdown, and commit references.

---

## Detailed Enhancement Descriptions

### 1. Transaction Safety Wrapper
**Priority:** 🔴 HIGH | **Effort:** 1 hour

**Problem:** If `run_payroll()` fails mid-execution (e.g., DB error during `store_payouts()`), partial payouts remain in the database, leaving the schedule in an inconsistent state.

**Solution:**
- Wrap the entire `run_payroll()` flow in a try/except with `db.rollback()` on failure
- Log the error and return a clear error summary to the user
- Ensure `clear_schedule_data()` + `store_payouts()` are atomic

**Location:** `app/services.py` → `PayrollService.run_payroll()`

---

### 2. Background Payroll Processing
**Priority:** 🔴 HIGH | **Effort:** 3-5 days

**Problem:** Large payroll runs (100+ models) block the UI for 30+ seconds. Browser may timeout. No progress indicator during calculation.

**Solution:**
- POST `/schedules/new` returns immediately with `run_id` and status "processing"
- Payroll calculation runs in a background task (threading or Celery/RQ)
- UI polls `/schedules/{run_id}/status` every 500ms for progress
- Schedule detail page shows "Calculating..." state until complete
- Consider WebSocket or SSE for real-time progress updates

**Location:** `app/routers/schedules.py`, `app/services.py`

**Trade-offs:**
- Threading: Simple, no extra infrastructure, but limited scalability
- Celery/RQ: Production-grade, requires Redis, more setup
- For current scale (< 500 models), threading is sufficient

---

### 3. Auto-Resolve Compensation Alerts
**Priority:** 🔴 HIGH | **Effort:** 2 days

**Problem:** Every mid-period compensation change creates an alert that requires manual UI resolution (Apply/Dismiss/Acknowledge). Common scenario (e.g., annual raises) generates many alerts.

**Solution:**
- On schedule refresh: if `new_amount` matches current `model.amount_monthly`, auto-dismiss the alert
- Add "Accept All" / "Dismiss All" batch action buttons
- Optional: email notification instead of manual review for non-critical changes

**Location:** `app/crud.py` → `create_compensation_alert()`, `app/routers/schedules.py`

---

### 4. Batch N+1 Query Optimization
**Priority:** 🟠 MEDIUM | **Effort:** 1-2 days

**Problem:** Dashboard loads 50 `ScheduleRun` records, then for each run executes 2 additional queries (payment summary + frequency breakdown) = 100 database round-trips. Mitigated by 5-minute cache, but still slow on cache miss.

**Solution:**
- Replace per-run queries with batch query using `WHERE run_id IN (...)`
- Pre-aggregate in SQL (SUM, COUNT, GROUP BY) instead of application layer
- Consider DB view or materialized summary for dashboard

**Location:** `app/routers/schedules.py` → `_gather_dashboard_data()`, `app/crud.py`

---

### 5. Re-Run Safeguard (Paid Payouts)
**Priority:** 🟠 MEDIUM | **Effort:** 1-2 days

**Problem:** Refreshing a schedule calls `clear_schedule_data()` which deletes `PayoutAdvanceAllocation` records. If a payout was already marked "paid" and allocations were realized, refreshing loses the audit trail of what was deducted from each payout.

**Solution:**
- Before clearing: check if any payouts have `status = "paid"` or `status = "approved"`
- If yes: warn the user with a confirmation dialog
- Snapshot allocation totals pre-clear for audit trail
- Consider making "paid" payouts immutable (skip on refresh, only recalculate "not_paid")

**Location:** `app/services.py` → `run_payroll()`, `app/crud.py` → `clear_schedule_data()`

---

### 6. Advance Deduction Confirmation
**Priority:** 🟠 MEDIUM | **Effort:** 1 day

**Problem:** When a user marks a payout as "paid", advance allocations are silently realized. The user has no visibility into how much is being deducted from the model's advance balance.

**Solution:**
- Before status change to "paid": fetch and display allocation breakdown
- Show confirmation modal if deduction > 10% of gross payout
- Toast notification after marking paid: "Advance repayment of $XXX applied to [Model]"

**Location:** `app/templates/schedules/detail.html`, `app/routers/schedules.py`

---

### 7. Exclude "Approved" from Overdue Count ✅
**Priority:** 🟢 LOW | **Effort:** 30 minutes | **Status:** Already implemented

**Implemented:** All overdue calculations already filter `status.in_(["not_paid", "on_hold"])` — "approved" payouts are never counted as overdue. Verified in crud.py dashboard_summary, schedules.py view, and status update endpoints.

---

### 8. Advance Deduction Toast on Paid
**Priority:** 🟢 LOW | **Effort:** 2 hours

**Problem:** After marking a payout as "paid", the user gets no feedback about advance deductions that were applied.

**Solution:**
- API response includes `{ advance_deducted: 150.00, advance_name: "..." }`
- UI shows toast notification: "Advance repayment of $150.00 applied"
- Dashboard badge updates to reflect new advance balance

**Location:** `app/routers/schedules.py`, `app/templates/schedules/detail.html`

---

### 9. Bulk Compensation Alert Resolution
**Priority:** 🟢 LOW | **Effort:** 3 hours

**Problem:** When multiple models receive compensation changes (e.g., annual review), each alert must be resolved individually.

**Solution:**
- Add "Accept All" button to alerts panel
- Add "Dismiss All" button for non-applicable changes
- Batch POST endpoint: `/compensation-alerts/bulk-resolve`

**Location:** `app/templates/schedules/detail.html`, `app/routers/schedules.py`

---

### 10. Bulk Advance Approval Workflow
**Priority:** 🟢 LOW | **Effort:** 1 day

**Problem:** Advances must be approved and activated one-by-one.

**Solution:**
- Add checkbox selection to advances list
- Bulk approve/activate endpoint
- Confirmation step showing total advance amounts

**Location:** `app/routers/advances.py`, `app/templates/advances/`

---

### 11. Export Cache with ETag
**Priority:** 🟢 LOW | **Effort:** 1 day

**Problem:** Export downloads regenerate the DataFrame and write files every time, even if nothing changed.

**Solution:**
- Cache generated export files with hash-based ETag
- Invalidate cache when payouts are modified
- Return 304 Not Modified for unchanged exports

**Location:** `app/routers/schedules.py` → `download_export()`

---

### 12. Unify Admin User Management Styling
**Priority:** 🟠 MED | **Effort:** 2-3 hours

**Problem:** `users.html` and `user_form.html` use large inline `<style>` blocks with their own class names (`.admin-container`, `.btn-edit`, `.users-table`) instead of the app's shared design system (`.card`, `.data-table`, `.button`, `.button--primary`). This causes visual inconsistency — user management pages look different from the rest of the app.

**Solution:**
- Replace inline styles with existing CSS classes from the design system
- Remove all `<style>` blocks from both templates
- Ensure responsive behavior matches other pages

**Location:** `app/templates/admin/users.html`, `app/templates/admin/user_form.html`

---

### 13. Admin Audit Log Viewer
**Priority:** 🟠 MED | **Effort:** 3-4 hours

**Problem:** The `AuditLog` model records admin actions (purge, config changes, cleanups, resets) but there's no UI to view these logs. Admins must query the database directly.

**Solution:**
- Add `GET /admin/audit-log` route with paginated log viewer
- Show: timestamp, user, action, details (collapsible JSON)
- Add filters by action type and date range
- Link from Admin Settings page

**Location:** `app/routers/admin.py`, new template `app/templates/admin/audit_log.html`

---

### 14. CSRF Protection on Admin Forms ✅
**Priority:** 🔴 HIGH | **Effort:** 2-3 hours | **Status:** Done

**Implemented:**
- HMAC-SHA256 CSRF tokens cryptographically bound to session cookies (`app/security.py`)
- `csrf_token()` Jinja2 global generates tokens; `<meta name="csrf-token">` in `base.html`
- Auto-inject JS adds hidden `_csrf_token` field to every `<form method="post">` at page load
- `verify_csrf` app-level FastAPI dependency validates tokens on all POST/PUT/DELETE/PATCH requests
- Login and API paths exempted; unauthenticated requests skip token check (auth rejects separately)
- Existing Origin/Referer middleware retained as additional layer
- `csrf_token_for(client)` test helper in `conftest.py`; 6 dedicated tests in `test_csrf_protection.py`

---

### 15. Pay Config UX Improvements
**Priority:** 🟢 LOW | **Effort:** 3-4 hours

**Problem:** Pay days input requires raw JSON (`[7, 14, 21, "eom"]`) — error-prone and non-intuitive. No validation feedback or preview of resulting pay dates.

**Solution:**
- Replace raw JSON input with visual day picker (checkboxes for 1-31 + EOM toggle)
- Add client-side validation with error messages
- Show a sample month preview of configured pay dates
- Keep JSON as internal format

**Location:** `app/templates/admin/settings.html`

---

### 16. Password Reset UX Improvements
**Priority:** 🟢 LOW | **Effort:** 1-2 hours

**Problem:** Password reset is an inline field in the users table — visible on screen. No confirmation field or strength requirements shown.

**Solution:**
- Move password reset to a modal or dedicated page
- Add "confirm password" field
- Show password strength indicator/requirements
- Add success/error feedback

**Location:** `app/templates/admin/users.html`, `app/routers/admin.py`

---

### 17. Frequency Plan Computed Dates Preview
**Priority:** 🟢 LOW | **Effort:** 1-2 hours

**Problem:** Pay day indices (`[0,1,2,3]`) are abstract 0-based array positions. Admin must mentally map these to actual pay dates from the pay config.

**Solution:**
- Show computed pay dates inline (e.g., "7th, 14th, 21st, EOM") next to each frequency plan
- Auto-update preview when indices are modified
- Reference the current pay config to resolve dates

**Location:** `app/templates/admin/settings.html`

---

### 18. Password Reset Should Auto-Unlock ✅
**Priority:** 🔴 HIGH | **Effort:** 15 minutes | **Status:** Already implemented

**Implemented:** The `reset_user_password()` handler in `app/routers/admin.py` already calls `unlock_account(db, user.username)` when `user.is_locked` is True.

---

### 19. Unauthorized Export Route Protection ✅
**Priority:** 🔴 HIGH | **Effort:** 30 minutes | **Status:** Already implemented

**Implemented:** All export routes (`/models/export`, `/dashboard/export`, `/dashboard/export-xlsx`, `/schedules/all-table/export`, `/schedules/export`) already include `user: User = Depends(get_current_user)`.

---

### 20. Payout Duplicate Prevention
**Priority:** 🟠 MED | **Effort:** 1 hour

**Problem:** No unique constraint on `(schedule_run_id, model_id, pay_date)` in the Payout model. If an endpoint is called twice (e.g., double-click), duplicate payout records can be created.

**Solution:** Add `UniqueConstraint("schedule_run_id", "model_id", "pay_date")` to the Payout model and create an Alembic migration.

**Location:** `app/models.py` (Payout), new migration

---

### 21. Soft-Delete Filter Enforcement ✅
**Priority:** 🟠 MED | **Effort:** 2-3 hours | **Status:** Already implemented

**Implemented:** `crud.get_model(db, model_id, include_deleted=False)` already filters `deleted_at IS NULL` by default. All route handlers in `models.py` use this function (9 call sites verified), so soft-deleted models return 404 on direct URL access.

---

### 22. Division by Zero Guard in Dashboard ✅
**Priority:** 🔴 HIGH | **Effort:** 15 minutes | **Status:** Already implemented

**Implemented:** `app/routers/models.py` already has `if active_count:` guard before the `total_paid_sum / Decimal(active_count)` division.

---

### 23. Import Error Display in UI
**Priority:** 🟠 MED | **Effort:** 1-2 hours

**Problem:** Excel importer collects validation errors in `ImportSummary.model_errors` but the UI only shows success counts ("3 models created"). Users don't see which rows failed or why.

**Solution:** Pass error summary list to the import result template and display individual row errors.

**Location:** `app/importers/excel_importer.py`, import result template

---

### 24. Excel Importer Sheet Name Validation
**Priority:** 🟢 LOW | **Effort:** 30 minutes

**Problem:** If user uploads an Excel file with a typo in the sheet name (e.g., "Model" instead of "Models"), the importer silently skips the data. User thinks import succeeded but nothing happened.

**Solution:** Check for expected sheet names and return an error listing which sheets were expected vs found.

**Location:** `app/importers/excel_importer.py`

---

### 25. Populate gross_amount on Payouts
**Priority:** 🟠 MED | **Effort:** 1-2 hours

**Problem:** `Payout.gross_amount` field exists (nullable) but is never populated during payout creation. When advances are deducted from `payout.amount`, the original gross amount is lost — making it impossible to reconstruct pre-deduction values.

**Solution:** Set `gross_amount = amount` during payout creation, before any advance deductions are applied.

**Location:** `app/services.py` → payout creation, `app/crud.py`

---

### 26. Commission Payouts in XLSX Export
**Priority:** 🟢 LOW | **Effort:** 1-2 hours

**Problem:** The XLSX export includes Models, Payouts, and Adjustments sheets but does not include CommissionPayout records. Commission data is only visible in the web UI.

**Solution:** Add a "Commission Payouts" sheet to the XLSX exporter.

**Location:** `app/exporting/xlsx.py`

---

### 27. Empty State Messages for Lists
**Priority:** 🟢 LOW | **Effort:** 1 hour

**Problem:** When no models or schedules exist, the list pages show blank content. New users may think the page is broken or still loading.

**Solution:** Add `{% if not items %}<div class="empty-state">...</div>{% endif %}` with helpful messages and CTAs (e.g., "No models yet. Import your first roster.").

**Location:** `app/templates/models/list.html`, `app/templates/schedules/list.html`

---

### 28. Session Secret Production Guard ✅
**Priority:** 🔴 HIGH | **Effort:** 15 minutes | **Status:** Already implemented

**Implemented:** `app/routers/auth.py` already raises `RuntimeError("SESSION_SECRET or SECRET_KEY must be set in production")` when `ENVIRONMENT == "production"` and the default secret is in use.

---

### 29. Update Docs for PostgreSQL-Only
**Priority:** 🟢 LOW | **Effort:** 30 minutes

**Problem:** `ALEMBIC_GUIDE.md`, `MIGRATION_GUIDE.md`, and other docs still reference SQLite development patterns. SQLite support was removed.

**Solution:** Update all docs to reflect PostgreSQL-only stack.

**Location:** `docs/ALEMBIC_GUIDE.md`, `docs/MIGRATION_GUIDE.md`, `docs/TECHNICAL_SPEC.md`

---

## System Flow Reference

```
Schedule Creation → Pay Calculation → Advance Allocation → Payout Storage → Status Management → Export
     (Form POST)      (payroll.py)       (crud.py)          (crud.py)        (AJAX/UI)        (CSV/Excel)
                                                                                 │
                                                                    On "paid" ──→ Realize Allocations
                                                                                 (advance balance reduced)
```

**Architecture Layers:**
```
Routes (schedules.py) → Services (services.py) → Core (payroll.py) + CRUD (crud.py) → DB (models.py)
```

**Payment Frequency Plans:**
| Plan | Pay Dates | Split |
|------|-----------|-------|
| Weekly | 7th, 14th, 21st, EOM | ¼ each |
| Biweekly | 14th, EOM | ½ each |
| Monthly | EOM | Full amount |
| Semimonthly | 14th, EOM | ½ each |
