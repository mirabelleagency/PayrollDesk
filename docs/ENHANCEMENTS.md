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

| #  | Enhancement                          | Priority | Effort   | Status      |
|----|--------------------------------------|----------|----------|-------------|
| 1  | Transaction safety wrapper           | 🔴 HIGH  | 1 hour   | ⬜ Pending  |
| 2  | Background payroll processing        | 🔴 HIGH  | 3-5 days | ⬜ Pending  |
| 3  | Auto-resolve compensation alerts     | 🔴 HIGH  | 2 days   | ⬜ Pending  |
| 4  | Batch N+1 query optimization         | 🟠 MED   | 1-2 days | ⬜ Pending  |
| 5  | Re-run safeguard (paid payouts)      | 🟠 MED   | 1-2 days | ⬜ Pending  |
| 6  | Advance deduction confirmation       | 🟠 MED   | 1 day    | ⬜ Pending  |
| 7  | Exclude "approved" from overdue      | 🟢 LOW   | 30 min   | ⬜ Pending  |
| 8  | Advance deduction toast on paid      | 🟢 LOW   | 2 hours  | ⬜ Pending  |
| 9  | Bulk compensation alert resolution   | 🟢 LOW   | 3 hours  | ⬜ Pending  |
| 10 | Bulk advance approval workflow       | 🟢 LOW   | 1 day    | ⬜ Pending  |
| 11 | Export cache with ETag               | 🟢 LOW   | 1 day    | ⬜ Pending  |

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

### 7. Exclude "Approved" from Overdue Count
**Priority:** 🟢 LOW | **Effort:** 30 minutes

**Problem:** Payouts with `status = "approved"` and a past `pay_date` are counted in the "overdue" metric. Semantically, "approved" means "ready to pay" — not "forgotten/unpaid."

**Solution:**
- Change overdue filter to only count `status = "not_paid"` with past `pay_date`
- "Approved" payouts with past dates should show as "pending payment" instead

**Location:** `app/routers/schedules.py` → `view_schedule()` overdue calculation

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
