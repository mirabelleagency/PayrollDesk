# PayrollDesk System Issues & Fix Plan

**Created:** December 24, 2025  
**Status:** Brainstorming / Pre-Implementation  
**Author:** AI Assistant

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Issues (Data Loss Risk)](#critical-issues)
3. [High Priority Issues (Code Quality)](#high-priority-issues)
4. [Medium Priority Issues (Best Practices)](#medium-priority-issues)
5. [Proposed Solutions](#proposed-solutions)
6. [Implementation Phases](#implementation-phases)
7. [Risk Assessment](#risk-assessment)
8. [Open Questions](#open-questions)

---

## Executive Summary

PayrollDesk has **3 critical issues** that can cause data loss, **5 high-priority** code quality issues, and **6 medium-priority** best practice violations. The most likely cause of reported data loss is the **non-atomic transaction pattern** in payroll regeneration.

### Issue Severity Distribution

```
🔴 Critical (Data Loss):     3 issues
🟡 High (Maintainability):   5 issues  
🟢 Medium (Best Practices):  6 issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:                       14 issues
```

---

## Critical Issues

### Issue #1: Non-Atomic Transaction in Payroll Regeneration 🔴

**Location:** `app/services.py` lines 56-127, `app/crud.py` line 320-326

**Current Flow:**
```
┌─────────────────────────────────────────────────────────────┐
│  1. capture_schedule_run_snapshot(db, run)  ← Good: backup  │
│  2. Save old payout status to memory                        │
│  3. crud.clear_schedule_data(db, run)                       │
│     └── db.commit() ← 🔴 COMMITS DELETE HERE!               │
│  4. models = crud.list_models()             ← Could fail    │
│  5. build_pay_schedule()                    ← Could fail    │
│  6. crud.store_payouts()                    ← Could fail    │
│  7. db.commit()                             ← Final commit  │
└─────────────────────────────────────────────────────────────┘
```

**The Problem:**

If steps 4-6 fail after step 3 commits the delete:
- Old payouts are **permanently deleted**
- New payouts were **never created**
- User sees empty schedule run
- Snapshot exists but requires **manual restore**

**Evidence in Code:**

```python
# app/crud.py lines 320-326
def clear_schedule_data(db: Session, schedule_run: ScheduleRun) -> None:
    db.query(PayoutAdvanceAllocation).filter(...).delete(synchronize_session=False)
    db.query(Payout).filter(...).delete()
    db.query(ValidationIssue).filter(...).delete()
    db.commit()  # ← Point of no return!
```

```python
# app/services.py line 76
crud.clear_schedule_data(self.db, run)  # Commits delete
# ... then 50 more lines of code that could fail ...
```

**Proposed Fix:**

Option A: **Defer commit until everything succeeds**
```python
def clear_schedule_data(db: Session, schedule_run: ScheduleRun) -> None:
    db.query(PayoutAdvanceAllocation).filter(...).delete(synchronize_session=False)
    db.query(Payout).filter(...).delete()
    db.query(ValidationIssue).filter(...).delete()
    db.flush()  # ← Flush to DB but don't commit yet
    # Caller commits after all operations succeed
```

Option B: **Wrap entire operation in try/except with rollback**
```python
def run_payroll(self, ...):
    try:
        # Capture snapshot first
        capture_schedule_run_snapshot(self.db, run)
        
        # Clear old data (no commit)
        self._clear_schedule_data_no_commit(run)
        
        # Generate new data
        new_payouts = self._generate_payouts(...)
        
        # Store new data
        self._store_payouts(new_payouts)
        
        # Single commit at the end
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise  # Re-raise so caller knows it failed
```

Option C: **Use database SAVEPOINT for nested transaction**
```python
def run_payroll(self, ...):
    savepoint = self.db.begin_nested()  # Create savepoint
    try:
        crud.clear_schedule_data(self.db, run)  # Within savepoint
        # ... generate payouts ...
        savepoint.commit()  # Commit savepoint
    except Exception:
        savepoint.rollback()  # Rollback to savepoint
        raise
```

**Recommended:** Option B - Most explicit and debuggable

**Effort:** 2-4 hours  
**Risk:** Medium (core flow change, needs thorough testing)

---

### Issue #2: Silent Exception Swallowing 🔴

**Locations:** 
- `app/routers/admin.py` - 8 occurrences
- `app/routers/schedules.py` - 1 occurrence (most dangerous)
- `app/crud.py` - 2 occurrences

**The Problem:**

```python
# app/routers/schedules.py line 1978
except Exception:
    # If refresh fails, continue to render the existing run rather than failing the page.
    pass  # ← User never knows refresh failed!
```

```python
# app/routers/admin.py (multiple places)
try:
    crud.log_admin_action(db, admin.id, "purge_model", {"impact": impact})
except Exception:
    pass  # ← Admin action not logged, no one knows
```

**Impact:**
- Failures are invisible
- No error logs for debugging
- User thinks operation succeeded when it didn't
- Data loss goes unnoticed

**Proposed Fix:**

Replace all `except Exception: pass` with proper logging:

```python
import logging

logger = logging.getLogger(__name__)

# Instead of:
except Exception:
    pass

# Use:
except Exception as exc:
    logger.exception("Failed to refresh payroll run %s: %s", run_id, exc)
    # Optionally: flash message to user
    # Optionally: re-raise for critical operations
```

For the schedules.py case specifically:
```python
except Exception as exc:
    logger.exception("Payroll refresh failed for run %s", run_id)
    # Show error to user instead of silently continuing
    return templates.TemplateResponse(
        request,
        "schedules/run_detail.html",
        {"error": f"Refresh failed: {exc}", ...}
    )
```

**Effort:** 1-2 hours  
**Risk:** Low (additive change, no logic changes)

---

### Issue #3: No Backup Before Destructive Operations 🔴

**Location:** `app/crud.py` line 1482-1534

**The Problem:**

`reset_application_data()` deletes ALL models, payouts, schedules, advances without any backup:

```python
def reset_application_data(db: Session) -> dict[str, int]:
    # Just starts deleting...
    deleted["models"] = db.query(Model).delete(synchronize_session=False)
    deleted["payouts"] = db.query(Payout).delete(synchronize_session=False)
    # ... etc
    db.commit()  # Gone forever
```

**Impact:**
- One accidental click = total data loss
- Even with confirmation prompt, mistakes happen
- No recovery without external DB backup

**Proposed Fix:**

Option A: **Auto-export before reset**
```python
def reset_application_data(db: Session, backup_path: Path | None = None) -> dict[str, int]:
    # Create automatic backup
    if backup_path is None:
        backup_path = Path(f"data/backups/pre_reset_{datetime.now().isoformat()}.json")
    
    _export_all_data(db, backup_path)
    logger.info(f"Created backup at {backup_path} before reset")
    
    # Then proceed with delete...
```

Option B: **Soft-delete with delayed hard-delete**
```python
# Add deleted_at column to all tables
# Reset just sets deleted_at = now()
# Background job hard-deletes after 7 days
# Provides "undo" window
```

Option C: **Require backup confirmation**
```python
def reset_application_data(db: Session, backup_confirmed: bool = False) -> dict[str, int]:
    if not backup_confirmed:
        raise ValueError("Must confirm backup exists before reset")
    # ...
```

**Recommended:** Option A - Automatic backup is safest

**Effort:** 4-6 hours  
**Risk:** Low (additive safety feature)

---

## High Priority Issues

### Issue #4: God Module (crud.py = 1,534 lines) 🟡

**The Problem:**

One file handles ALL database operations for 8+ domains:
- Models (250 lines)
- Payouts (350 lines)
- Schedule Runs (200 lines)
- Advances (300 lines)
- Dashboard/Stats (200 lines)
- Ad-hoc Payments (150 lines)
- Admin/Maintenance (100 lines)

**Impact:**
- Hard to navigate
- Merge conflicts
- Difficult to test individual domains
- Cognitive overload

**Proposed Fix:**

Split into domain modules:

```
app/
├── crud/
│   ├── __init__.py       # Re-exports for backward compatibility
│   ├── models.py         # Model CRUD operations
│   ├── payouts.py        # Payout operations
│   ├── schedules.py      # Schedule run operations
│   ├── advances.py       # Advance operations
│   ├── dashboard.py      # Dashboard queries
│   ├── adhoc.py          # Ad-hoc payment operations
│   └── admin.py          # Admin/maintenance operations
```

**Backward Compatibility:**
```python
# app/crud/__init__.py
from app.crud.models import *
from app.crud.payouts import *
from app.crud.schedules import *
from app.crud.advances import *
from app.crud.dashboard import *
from app.crud.adhoc import *
from app.crud.admin import *

# All existing imports like `from app import crud` still work
# crud.list_models() still works
```

**Effort:** 8-12 hours  
**Risk:** Medium (many file changes, but logic unchanged)

---

### Issue #5: Monster Function (dashboard_summary = 198 lines) 🟡

**Location:** `app/crud.py` lines 672-870

**The Problem:**

Single function doing 12+ different queries:
1. Model counts by status
2. Total schedule runs
3. Latest run
4. Current month run
5. Payout metrics
6. Monthly burn calculation
7. Run rate calculation
8. Year total paid
9. Previous month metrics
10. Month-over-month change
11. Overdue payments
12. On-hold payments
13. Average per model

**Impact:**
- Multiple DB round-trips
- Hard to test individual metrics
- Hard to cache
- Performance bottleneck

**Proposed Fix:**

Break into smaller, focused functions:

```python
# app/crud/dashboard.py

def get_model_counts(db: Session) -> dict[str, int]:
    """Get counts of models by status."""
    ...

def get_current_month_metrics(db: Session) -> dict:
    """Get metrics for current month's payroll run."""
    ...

def get_payment_alerts(db: Session) -> dict:
    """Get overdue and on-hold payment counts."""
    ...

def dashboard_summary(db: Session) -> dict:
    """Aggregate all dashboard metrics."""
    return {
        **get_model_counts(db),
        **get_current_month_metrics(db),
        **get_payment_alerts(db),
    }
```

**Optional Enhancement:** Add caching
```python
from functools import lru_cache
from datetime import datetime, timedelta

_cache = {}
_cache_ttl = timedelta(minutes=5)

def dashboard_summary(db: Session) -> dict:
    cache_key = "dashboard_summary"
    if cache_key in _cache:
        data, timestamp = _cache[cache_key]
        if datetime.now() - timestamp < _cache_ttl:
            return data
    
    result = _compute_dashboard_summary(db)
    _cache[cache_key] = (result, datetime.now())
    return result
```

**Effort:** 4-6 hours  
**Risk:** Low (refactor, no logic change)

---

### Issue #6: N+1 Query Pattern 🟡

**Location:** `app/crud.py` `cleanup_empty_runs()` function

**The Problem:**

```python
def cleanup_empty_runs(db: Session) -> dict:
    runs = db.execute(select(ScheduleRun.id)).scalars().all()
    for run_id in runs:
        count = db.execute(  # ← Query per iteration!
            select(func.count()).where(Payout.schedule_run_id == run_id)
        ).scalar_one() or 0
        if count == 0:
            # delete...
```

If there are 100 runs, this executes 101 queries (1 + 100).

**Impact:**
- Poor performance at scale
- Database load
- Slow maintenance operations

**Proposed Fix:**

Single query with aggregation:

```python
def cleanup_empty_runs(db: Session) -> dict:
    # Get all runs with their payout counts in ONE query
    subq = (
        select(Payout.schedule_run_id, func.count().label('cnt'))
        .group_by(Payout.schedule_run_id)
        .subquery()
    )
    
    # Find runs with 0 payouts (left join, null count)
    empty_runs = db.execute(
        select(ScheduleRun.id)
        .outerjoin(subq, ScheduleRun.id == subq.c.schedule_run_id)
        .where(func.coalesce(subq.c.cnt, 0) == 0)
    ).scalars().all()
    
    # Batch delete
    if empty_runs:
        deleted = db.query(ScheduleRun).filter(
            ScheduleRun.id.in_(empty_runs)
        ).delete(synchronize_session=False)
    
    db.commit()
    return {"deleted_runs": len(empty_runs)}
```

**Effort:** 1-2 hours  
**Risk:** Low (performance improvement, same behavior)

---

### Issue #7: Complex Nested Logic in Advance Allocation 🟡

**Location:** `app/crud.py` lines 1378-1455

**The Problem:**

Triple-nested loops with complex business logic:

```python
def _apply_advance_allocations_for_run(db, run, payouts):
    for model_id, rows in by_model.items():        # Loop 1
        for payout in rows:                         # Loop 2
            for adv in advances:                    # Loop 3
                if (adv.strategy or "fixed") == "fixed":
                    # 15 lines of calculation
                else:
                    # 10 lines of calculation
                # More logic...
```

**Impact:**
- Hard to understand
- Hard to test edge cases
- Bug-prone
- Performance concerns

**Proposed Fix:**

Extract to dedicated service class:

```python
# app/services/advance_allocator.py

@dataclass
class AllocationPlan:
    payout_id: int
    advance_id: int
    amount: Decimal

class AdvanceAllocator:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_single_allocation(
        self, 
        advance: ModelAdvance, 
        gross_amount: Decimal
    ) -> Decimal:
        """Calculate allocation amount based on strategy."""
        if advance.strategy == "fixed":
            return min(advance.fixed_amount, advance.amount_remaining)
        else:
            pct = advance.percent_rate / Decimal("100")
            return min(gross_amount * pct, advance.amount_remaining)
    
    def plan_allocations(
        self, 
        payouts: list[Payout], 
        advances: list[ModelAdvance]
    ) -> list[AllocationPlan]:
        """Generate allocation plan (pure calculation, no side effects)."""
        plans = []
        # Cleaner logic here...
        return plans
    
    def apply_to_run(self, run: ScheduleRun, payouts: list[Payout]) -> None:
        """Apply allocations to a schedule run."""
        advances = self._get_pending_advances(payouts)
        plans = self.plan_allocations(payouts, advances)
        self._create_allocation_records(plans)
        self.db.flush()
```

**Effort:** 6-8 hours  
**Risk:** Medium (core business logic, needs testing)

---

### Issue #8: Cookie Secure Flag Logic ✅ FIXED

**Location:** `app/routers/auth.py` line 105

**Was:**
```python
is_production = os.getenv("PAYROLL_DATABASE_URL", "").startswith("postgresql")
```

**Now:**
```python
env = os.getenv("ENVIRONMENT", "production").lower()
is_production = env not in ("development", "dev", "local", "test")
```

**Status:** Fixed during this session

---

## Medium Priority Issues

### Issue #9: Duplicate Query Patterns 🟢

Multiple `count_models_by_*` functions with same signature and pattern.

**Proposed Fix:** Generic grouped counting function
```python
def count_models_grouped_by(db: Session, group_field: str, **filters) -> dict[str, int]:
    field = getattr(Model, group_field)
    stmt = select(field, func.count()).group_by(field)
    # Apply filters...
    return dict(db.execute(stmt).all())
```

---

### Issue #10: Business Logic in CRUD Layer 🟢

`create_model()` auto-creates compensation adjustment.

**Proposed Fix:** Move to service layer
```python
# CRUD: Pure data access
def create_model(db, payload):
    model = Model(**payload.model_dump())
    db.add(model)
    return model

# Service: Business logic
def register_model(db, payload):
    model = crud.create_model(db, payload)
    crud.create_initial_compensation(db, model)
    db.commit()
    return model
```

---

### Issue #11: Inconsistent Error Handling 🟢

Some functions return `None`, others raise `ValueError`.

**Proposed Fix:** Standardize pattern
- `get_*` functions return `None` if not found
- `create_*` functions raise `ValueError` for business rule violations
- Document the pattern

---

### Issue #12: Hardcoded Constants 🟢

```python
ADVANCE_DEFAULT_MIN_FLOOR = Decimal("500")
ADVANCE_DEFAULT_MAX_PER_RUN = Decimal("600")
ADVANCE_DEFAULT_CAP_MULTIPLIER = Decimal("1.0")
```

**Proposed Fix:** Move to config
```python
# app/config.py
class AdvanceConfig:
    MIN_FLOOR = Decimal(os.getenv("ADVANCE_MIN_FLOOR", "500"))
    MAX_PER_RUN = Decimal(os.getenv("ADVANCE_MAX_PER_RUN", "600"))
    CAP_MULTIPLIER = Decimal(os.getenv("ADVANCE_CAP_MULTIPLIER", "1.0"))
```

---

### Issue #13: Missing Docstrings 🟢

Many functions lack documentation.

**Proposed Fix:** Add docstrings during refactoring

---

### Issue #14: Inline Import 🟢

`from typing import Any` at line 1014.

**Proposed Fix:** Move to top of file with other imports

---

## Implementation Phases

### Phase 1: Stop Data Loss (Week 1)

| Task | Issue | Effort | Risk |
|------|-------|--------|------|
| Fix non-atomic transaction | #1 | 4h | Medium |
| Add exception logging | #2 | 2h | Low |
| Add pre-reset backup | #3 | 4h | Low |

**Total:** ~10 hours

### Phase 2: Improve Maintainability (Week 2-3)

| Task | Issue | Effort | Risk |
|------|-------|--------|------|
| Split crud.py | #4 | 12h | Medium |
| Break down dashboard_summary | #5 | 6h | Low |
| Fix N+1 queries | #6 | 2h | Low |
| Refactor advance allocation | #7 | 8h | Medium |

**Total:** ~28 hours

### Phase 3: Polish (Week 4)

| Task | Issue | Effort | Risk |
|------|-------|--------|------|
| Consolidate duplicate patterns | #9 | 2h | Low |
| Extract business logic | #10 | 4h | Low |
| Standardize error handling | #11 | 2h | Low |
| Move constants to config | #12 | 1h | Low |
| Add docstrings | #13 | 2h | Low |
| Fix inline import | #14 | 5m | Low |

**Total:** ~11 hours

---

## Risk Assessment

### Critical Flow Analysis: What Could Break

#### Scenario A: Payroll Regeneration Failure

**Current Flow (Dangerous):**
```
User clicks "Refresh" on schedule run
    ↓
services.run_payroll() called
    ↓
capture_schedule_run_snapshot()     ← ✅ Backup created
    ↓
crud.clear_schedule_data()          ← 🔴 COMMITS DELETE
    ↓
crud.list_models()                  ← ⚠️ Could fail (DB timeout)
    ↓
build_pay_schedule()                ← ⚠️ Could fail (bad data)
    ↓
crud.store_payouts()                ← ⚠️ Could fail (FK error)
```

**Failure Scenarios:**

| Failure Point | What Happens | Data Lost? |
|---------------|--------------|------------|
| DB timeout after delete | Old payouts gone, new never created | **YES** |
| Invalid model data | Payroll calculation fails mid-way | **YES** |
| Constraint violation | store_payouts() partially completes | **Partial** |
| Memory error | Process crashes after delete | **YES** |
| App restart (uvicorn) | Mid-operation restart | **YES** |

**Real World Triggers:**
- Large number of models (memory pressure)
- PostgreSQL connection pool exhaustion
- Worker process killed by Render
- Network blip to database
- Invalid date in model record

---

#### Scenario B: Silent Exception Masks Failure

**Location:** `app/routers/schedules.py` line 1978

```python
try:
    run = payroll_svc.run_payroll(...)
    run = crud.get_schedule_run(db, refreshed_run_id)
except Exception:
    pass  # ← User sees stale data, thinks it worked
```

**What User Sees vs Reality:**

| User Sees | Actual State |
|-----------|--------------|
| "Schedule refreshed" | No change, old data shown |
| December payroll page | Empty (data was deleted) |
| Same numbers as before | Calculation failed silently |

---

#### Scenario C: Admin Reset with No Undo

**Location:** `app/crud.py` line 1482

```python
result = crud.reset_application_data(db)
# → 54 models deleted
# → 393 payouts deleted
# → 3 schedule runs deleted
# → No backup, no undo
```

**Only Recovery:** Restore from external database backup (if one exists)

---

### Impact Matrix: What Each Fix Could Break

#### Fix #1: Remove commit from clear_schedule_data()

**Change:**
```python
# Before
db.commit()

# After  
db.flush()  # Caller must commit
```

**Could Break:**
| Component | Risk | Mitigation |
|-----------|------|------------|
| services.run_payroll() | Needs to add commit | Already commits later |
| snapshots.restore_latest_schedule_snapshot() | Calls clear_schedule_data | Check if commits after |
| Any direct crud.clear_schedule_data() calls | Must now commit | Search and update |

**Dependencies to Check:**
```
grep -r "clear_schedule_data" --include="*.py"
→ services.py (line 76)
→ snapshots.py (line 373)
→ test files
```

**Risk Level:** Medium - 2 production callers, both need verification

---

#### Fix #2: Add Exception Logging

**Change:**
```python
# Before
except Exception:
    pass

# After
except Exception as exc:
    logger.exception("Operation failed: %s", exc)
```

**Could Break:**
| Component | Risk | Mitigation |
|-----------|------|------------|
| Nothing | Low | Additive change |
| Log volume | Low | Structured logging |

**Risk Level:** Very Low - no behavior change

---

#### Fix #3: Add Pre-Reset Backup

**Change:**
```python
def reset_application_data(db, backup_path=None):
    # New: Export before delete
    _export_all_data(db, backup_path)
    # Then delete...
```

**Could Break:**
| Component | Risk | Mitigation |
|-----------|------|------------|
| Disk space | Low | Clean up old backups |
| Export failure blocks reset | Low | Make backup optional |
| Performance | Low | Export is fast |

**Risk Level:** Low - additive safety feature

---

#### Fix #4: Split crud.py into Modules

**Change:**
```
app/crud.py (1534 lines)
    ↓
app/crud/
    __init__.py
    models.py
    payouts.py
    schedules.py
    ...
```

**Could Break:**
| Component | Risk | Mitigation |
|-----------|------|------------|
| All imports | Medium | Re-export from __init__.py |
| Circular imports | Medium | Careful dependency ordering |
| IDE autocomplete | Low | May need restart |
| Existing tests | Medium | Should still pass |

**Verification Required:**
```bash
# After split, verify all imports still work
python -c "from app import crud; print(dir(crud))"

# Run full test suite
pytest
```

**Risk Level:** Medium - many files affected, but no logic change

---

### Dependency Graph: What Calls What

```
┌─────────────────────────────────────────────────────────┐
│                    ROUTERS (UI Layer)                   │
├─────────────────────────────────────────────────────────┤
│  schedules.py ──→ services.run_payroll()               │
│       ↓                    ↓                            │
│  models.py ────→ crud.create_model()                   │
│       ↓                    ↓                            │
│  admin.py ─────→ crud.reset_application_data()         │
│       ↓                    ↓                            │
│  dashboard.py ─→ crud.dashboard_summary()              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   SERVICES Layer                        │
├─────────────────────────────────────────────────────────┤
│  PayrollService.run_payroll()                          │
│       ↓                                                 │
│  crud.clear_schedule_data() ← 🔴 DANGER POINT          │
│       ↓                                                 │
│  crud.store_payouts()                                  │
│       ↓                                                 │
│  snapshots.capture_schedule_run_snapshot()             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                     CRUD Layer                          │
├─────────────────────────────────────────────────────────┤
│  70+ functions across 8 domains                         │
│  1,534 lines in single file                            │
│  Mixed responsibilities                                 │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   MODELS Layer                          │
├─────────────────────────────────────────────────────────┤
│  Model, Payout, ScheduleRun, etc.                      │
│  SQLAlchemy ORM definitions                            │
│  Cascade delete relationships                          │
└─────────────────────────────────────────────────────────┘
```

---

### Safe Implementation Order

**Phase 1A: Lowest Risk First**
1. Add logging (Fix #2) - no behavior change
2. Add backup (Fix #3) - additive safety

**Phase 1B: Transaction Fix**  
3. Fix clear_schedule_data (Fix #1) - requires testing

**Phase 2: Refactoring**
4. Split crud.py (Fix #4) - big but safe change

---

### Pre-Implementation Checklist

Before starting:

- [ ] Backup production database
- [ ] Verify all tests pass: `pytest`
- [ ] Document current behavior
- [ ] Set up staging environment

Before each fix:

- [ ] Write test for the fix
- [ ] Apply fix
- [ ] Run test suite
- [ ] Manual verification
- [ ] Document changes

After all fixes:

- [ ] Full regression test
- [ ] Performance check (dashboard_summary)
- [ ] Deploy to staging
- [ ] Monitor for 24h
- [ ] Deploy to production

---

## Implementation Checklist

### Prerequisites

- [ ] **PR-1:** Backup production database
- [ ] **PR-2:** Run full test suite: `pytest` - verify all pass
- [ ] **PR-3:** Create git branch: `git checkout -b fix/system-issues`
- [ ] **PR-4:** Verify Docker PostgreSQL running: `docker ps | grep payrolldesk_db`

---

### Phase 1A: Add Logging (Zero Risk)

**Goal:** Replace silent `except Exception: pass` with proper logging

#### Step 1A.1: Create Logger Module
- [ ] Create `app/logging_config.py`
```python
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("payrolldesk")
```

#### Step 1A.2: Update admin.py (8 locations)
- [ ] Line 286: Add logging for purge_model action
- [ ] Line 321: Add logging for cleanup_empty_runs action  
- [ ] Line 336: Add logging for cleanup_orphans action
- [ ] Line 359: Add logging for reset_application_data action
- [ ] Line 399: Add logging for diagnostics
- [ ] Line 415: Add logging for diagnostics
- [ ] Line 423: Add logging for diagnostics
- [ ] Line 481: Add logging for API purge_model

**Pattern to apply:**
```python
# Before
except Exception:
    pass

# After
except Exception as exc:
    logger.warning("Failed to log admin action %s: %s", action_name, exc)
```

#### Step 1A.3: Update schedules.py (CRITICAL - line 1978)
- [ ] Line 1978: Add logging AND user feedback for refresh failure
```python
# Before
except Exception:
    pass

# After
except Exception as exc:
    logger.exception("Payroll refresh failed for run %s", run_id)
    # Re-raise so user knows it failed
    raise HTTPException(
        status_code=500,
        detail=f"Payroll refresh failed: {exc}"
    )
```

#### Step 1A.4: Verification
- [ ] Run tests: `pytest tests/test_admin_*.py`
- [ ] Manual test: Trigger admin actions, check logs appear
- [ ] Commit: `git commit -m "feat: add logging to replace silent exceptions"`

---

### Phase 1B: Add Pre-Reset Backup (Low Risk)

**Goal:** Automatically backup data before destructive operations

#### Step 1B.1: Create Backup Utility
- [ ] Create `app/backup.py`
```python
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Model, Payout, ScheduleRun, ...

def export_all_data(db: Session) -> dict:
    """Export all domain data to a dictionary."""
    return {
        "exported_at": datetime.now().isoformat(),
        "models": [_serialize_model(m) for m in db.query(Model).all()],
        "payouts": [_serialize_payout(p) for p in db.query(Payout).all()],
        "schedule_runs": [...],
        # etc.
    }

def save_backup(db: Session, backup_dir: Path = Path("data/backups")) -> Path:
    """Export data and save to JSON file."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"backup_{timestamp}.json"
    
    data = export_all_data(db)
    path.write_text(json.dumps(data, indent=2, default=str))
    
    return path
```

#### Step 1B.2: Update reset_application_data()
- [ ] Modify `app/crud.py` line 1482:
```python
def reset_application_data(db: Session, skip_backup: bool = False) -> dict[str, int]:
    """Delete all model and payout data, with automatic backup."""
    from app.backup import save_backup
    
    backup_path = None
    if not skip_backup:
        backup_path = save_backup(db)
        logger.info("Created backup at %s before reset", backup_path)
    
    # Then proceed with delete...
    deleted = {}
    # ... existing code ...
    
    deleted["backup_path"] = str(backup_path) if backup_path else None
    return deleted
```

#### Step 1B.3: Create Restore Function
- [ ] Add to `app/backup.py`:
```python
def restore_backup(db: Session, backup_path: Path) -> dict:
    """Restore data from a backup file."""
    data = json.loads(backup_path.read_text())
    # ... restore logic ...
```

#### Step 1B.4: Verification
- [ ] Run tests: `pytest tests/test_admin_reset_data.py`
- [ ] Manual test: Reset data, verify backup created in `data/backups/`
- [ ] Test restore function
- [ ] Commit: `git commit -m "feat: add automatic backup before reset"`

---

### Phase 1C: Fix Non-Atomic Transaction (Medium Risk)

**Goal:** Ensure payroll regeneration is atomic (all-or-nothing)

#### Step 1C.1: Modify clear_schedule_data()
- [ ] Edit `app/crud.py` line 320:
```python
def clear_schedule_data(db: Session, schedule_run: ScheduleRun) -> None:
    """Clear payouts and validations for a schedule run.
    
    NOTE: Does NOT commit. Caller must commit after all operations succeed.
    """
    db.query(PayoutAdvanceAllocation).filter(...).delete(synchronize_session=False)
    db.query(Payout).filter(...).delete()
    db.query(ValidationIssue).filter(...).delete()
    db.flush()  # ← Changed from db.commit()
```

#### Step 1C.2: Update services.run_payroll()
- [ ] Edit `app/services.py` - wrap in try/except:
```python
def run_payroll(self, ...):
    try:
        # Existing code...
        if existing_runs:
            run = existing_runs[0]
            if run.payouts or run.validations:
                capture_schedule_run_snapshot(self.db, run, ...)
            for payout in run.payouts:
                # Save old data...
            crud.clear_schedule_data(self.db, run)  # No longer commits
        else:
            run = crud.create_schedule_run(...)
        
        # Generate new data (could fail)...
        models = crud.list_models(self.db)
        records = [...]
        schedule_df, summary = build_pay_schedule(...)
        
        # Store new data (could fail)...
        crud.store_payouts(...)
        crud.store_validation_messages(...)
        
        # Single commit at the end - all or nothing
        self.db.commit()
        
    except Exception as exc:
        self.db.rollback()
        logger.exception("Payroll generation failed, rolled back")
        raise  # Re-raise so caller can handle
```

#### Step 1C.3: Update snapshots.py
- [ ] Check `app/snapshots.py` line 373 - calls `clear_schedule_data`:
```python
def restore_latest_schedule_snapshot(...):
    # ...
    crud.clear_schedule_data(db, run)  # No longer commits
    # ... restore payouts ...
    db.commit()  # ← Must add explicit commit
```

#### Step 1C.4: Verification
- [ ] Write test for rollback behavior:
```python
def test_run_payroll_rollback_on_failure(test_db, monkeypatch):
    """Test that payroll regeneration rolls back on failure."""
    # Create initial run with payouts
    run = crud.create_schedule_run(...)
    crud.store_payouts(test_db, run, [...])
    test_db.commit()
    initial_count = len(list(run.payouts))
    
    # Patch to cause failure after delete
    def fail_build(*args, **kwargs):
        raise RuntimeError("Simulated failure")
    monkeypatch.setattr("app.core.payroll.build_pay_schedule", fail_build)
    
    # Attempt regeneration
    svc = PayrollService(test_db)
    with pytest.raises(RuntimeError):
        svc.run_payroll(...)
    
    # Verify payouts still exist (rollback worked)
    test_db.refresh(run)
    assert len(list(run.payouts)) == initial_count
```
- [ ] Run test
- [ ] Manual test: Trigger regeneration, verify works normally
- [ ] Manual test: Simulate failure, verify rollback
- [ ] Commit: `git commit -m "fix: make payroll regeneration atomic"`

---

### Phase 2: Split crud.py (Medium Risk, High Effort)

**Goal:** Split 1,534-line god module into domain modules

#### Step 2.1: Create Directory Structure
- [ ] Create `app/crud/` directory
- [ ] Create `app/crud/__init__.py`
- [ ] Create empty domain files:
  - `app/crud/models.py`
  - `app/crud/payouts.py`
  - `app/crud/schedules.py`
  - `app/crud/advances.py`
  - `app/crud/dashboard.py`
  - `app/crud/adhoc.py`
  - `app/crud/admin.py`

#### Step 2.2: Move Functions (One Domain at a Time)

**Models Domain:**
- [ ] Move from crud.py to crud/models.py:
  - `list_models()`
  - `count_models()`
  - `get_model()`
  - `get_model_by_code()`
  - `create_model()`
  - `update_model()`
  - `delete_model()`
  - `_model_filters()`
  - Related count functions
- [ ] Add imports to `crud/models.py`
- [ ] Export from `crud/__init__.py`
- [ ] Run tests: `pytest tests/test_*model*.py`

**Payouts Domain:**
- [ ] Move to crud/payouts.py:
  - `store_payouts()`
  - `list_payouts_for_run()`
  - `get_payout()`
  - `update_payout()`
  - `payout_codes_for_run()`
  - `payout_dates_for_run()`
  - `payout_status_counts()`
  - etc.
- [ ] Run tests: `pytest tests/test_*payout*.py`

**Schedules Domain:**
- [ ] Move to crud/schedules.py:
  - `create_schedule_run()`
  - `get_schedule_run()`
  - `list_schedule_runs()`
  - `delete_schedule_run()`
  - `clear_schedule_data()`
  - `run_payment_summary()`
- [ ] Run tests: `pytest tests/test_schedule*.py`

**Continue for remaining domains...**
- [ ] Advances
- [ ] Dashboard
- [ ] Ad-hoc
- [ ] Admin

#### Step 2.3: Update __init__.py for Backward Compatibility
- [ ] Edit `app/crud/__init__.py`:
```python
# Re-export everything for backward compatibility
from app.crud.models import *
from app.crud.payouts import *
from app.crud.schedules import *
from app.crud.advances import *
from app.crud.dashboard import *
from app.crud.adhoc import *
from app.crud.admin import *

# Also export named types if any
from app.crud.models import ReferralTermPayload
```

#### Step 2.4: Full Verification
- [ ] Run ALL tests: `pytest`
- [ ] Manual test: Dashboard loads
- [ ] Manual test: Model CRUD works
- [ ] Manual test: Schedule regeneration works
- [ ] Check import time: `python -c "import time; t=time.time(); from app import crud; print(f'{time.time()-t:.2f}s')"`
- [ ] Commit: `git commit -m "refactor: split crud.py into domain modules"`

#### Step 2.5: Delete Original crud.py
- [ ] Remove `app/crud.py` (now replaced by `app/crud/` package)
- [ ] Verify no import errors
- [ ] Final test run

---

### Phase 3: Polish (Low Risk)

#### Step 3.1: Fix Inline Import
- [ ] Move `from typing import Any` from line 1014 to top of file

#### Step 3.2: Add Missing Docstrings
- [ ] Add docstrings to functions in new crud modules during Phase 2

#### Step 3.3: Move Constants to Config
- [ ] Create `app/config.py` with advance defaults
- [ ] Update crud/advances.py to use config

---

### Post-Implementation

- [ ] Full regression test on staging
- [ ] Performance comparison (dashboard load time)
- [ ] Code review
- [ ] Merge PR
- [ ] Deploy to production
- [ ] Monitor for 24h
- [ ] Document changes in CHANGELOG.md

---

## Open Questions

1. **Transaction Strategy:** Should we use savepoints (Option C) for nested transaction support, or is simple try/except (Option B) sufficient?

2. **Backup Storage:** Where should automatic backups be stored?
   - Local filesystem (`data/backups/`)
   - Cloud storage (S3, GCS)
   - Separate database table

3. **Soft Delete:** Should we implement soft-delete for models/payouts as additional safety? This adds complexity but provides "undo" capability.

4. **Caching:** Should dashboard_summary use caching? If so:
   - What TTL? (5 min? 15 min?)
   - Redis or in-memory?
   - Cache invalidation strategy?

5. **Testing:** How much test coverage do we need before refactoring crud.py? Current coverage is unknown.

6. **Migration:** Should Phase 2 (crud split) be done all at once or incrementally (one domain at a time)?

---

## Next Steps

After brainstorming, decide on:

1. [ ] Confirm Phase 1 approach (Option A, B, or C for transaction fix)
2. [ ] Decide on backup storage location
3. [ ] Decide if soft-delete is worth the complexity
4. [ ] Set timeline expectations
5. [ ] Begin Phase 1 implementation

---

*Document created December 24, 2025*
