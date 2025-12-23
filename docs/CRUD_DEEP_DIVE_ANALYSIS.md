# crud.py Deep Dive Analysis

**File:** app/crud.py  
**Lines:** 1,534  
**Analysis Date:** December 24, 2025

---

## Executive Summary

`crud.py` is the data access layer for PayrollDesk. While it follows CRUD patterns and has good functionality, its size (1,534 lines) and organization create maintainability and readability challenges. This analysis identifies specific issues and provides actionable refactoring recommendations.

---

## 1. Overview Statistics

| Metric | Value | Assessment |
|--------|-------|------------|
| Total Lines | 1,534 | ⚠️ Too large |
| Functions | ~70 | ⚠️ Too many for one file |
| Domains Mixed | 8+ | ⚠️ Should be separated |
| Cyclomatic Complexity | Medium-High | 🟡 Some complex functions |
| Test Coverage | Unknown | ⚠️ Risk area |

### Domain Count by Function

| Domain | Functions | Lines (est.) |
|--------|-----------|--------------|
| Models | 15 | ~250 |
| Payouts | 20 | ~350 |
| Schedules | 12 | ~200 |
| Advances | 15 | ~300 |
| Dashboard/Stats | 8 | ~200 |
| Ad-hoc Payments | 8 | ~150 |
| Admin/Maintenance | 5 | ~100 |

---

## 2. Identified Issues

### Issue #1: God Module Anti-Pattern 🔴

**Problem:** Single file handles ALL database operations for 8+ domains.

**Evidence:**
```python
# All of these are in ONE file:
def list_models(...)      # Models domain
def list_payouts_for_run(...)  # Payouts domain
def create_schedule_run(...)   # Schedules domain
def create_advance(...)        # Advances domain
def dashboard_summary(...)     # Analytics domain
def create_adhoc_payment(...)  # Ad-hoc domain
def purge_model_hard(...)      # Admin domain
def reset_application_data(...)  # Maintenance domain
```

**Impact:**
- Hard to navigate (1,534 lines to scroll)
- Merge conflicts when multiple features touch CRUD
- Cognitive overload when reading
- Difficult to test individual domains

**Severity:** High

---

### Issue #2: dashboard_summary() is a Monster Function 🔴

**Problem:** Lines 672-870 (198 lines) - A single function doing too much.

**Evidence:**
```python
def dashboard_summary(db: Session) -> dict[str, Decimal | int | date | None]:
    # Model counts query
    model_counts_stmt = ...
    
    # Run queries
    total_runs = ...
    latest_run = ...
    current_month_run = ...
    
    # Payout metrics query
    payout_metrics_stmt = ...
    
    # Monthly burn calculation
    monthly_burn = ...
    
    # Run rate calculation
    run_rate = ...
    
    # Year total calculation
    year_total_paid = ...
    
    # Previous month metrics
    prev_month_run = ...
    
    # Month-over-month change
    burn_change_pct = ...
    
    # Overdue payments query
    overdue_count = ...
    overdue_payments_data = ...
    
    # On-hold payments query
    on_hold_payments_data = ...
    
    # Average per model
    avg_per_model = ...
    
    return {...23 keys...}
```

**Impact:**
- Multiple DB round-trips in one function
- No caching strategy
- Extremely hard to test
- Performance bottleneck on dashboard

**Severity:** High

---

### Issue #3: Duplicate Query Patterns 🟡

**Problem:** Similar filter logic repeated across functions.

**Evidence:**
```python
# Pattern repeats 5+ times
def count_models_by_status(db, code, status, frequency, payment_method):
    stmt = select(...)
    filters = _model_filters(...)  # Good - reuse
    ...

def count_models_by_payment_method(db, code, status, frequency, payment_method):
    stmt = select(...)
    filters = _model_filters(...)  # Same signature repeated
    ...

def count_models_by_frequency(db, code, status, frequency, payment_method):
    stmt = select(...)
    filters = _model_filters(...)  # Same signature repeated
    ...
```

**Better Approach:**
```python
# Generic grouped counting function
def count_models_grouped_by(
    db: Session,
    group_field: str,
    code: str | None = None,
    ...
) -> Dict[str, int]:
    field = getattr(Model, group_field)
    stmt = select(field, func.count()).group_by(field)
    ...
```

**Severity:** Medium

---

### Issue #4: Mixed Return Types 🟡

**Problem:** Inconsistent return type patterns.

**Evidence:**
```python
# Returns Model | None
def get_model(db: Session, model_id: int) -> Model | None:
    return db.get(Model, model_id)

# Returns ScheduleRun | None  
def get_schedule_run(db: Session, run_id: int) -> ScheduleRun | None:
    return db.get(ScheduleRun, run_id)

# But this raises ValueError instead of returning None
def create_schedule_run(...):
    existing = ...
    if existing:
        raise ValueError(...)  # Inconsistent with get_ pattern
```

**Impact:**
- Inconsistent error handling in callers
- Some operations raise, others return None

**Severity:** Low-Medium

---

### Issue #5: Business Logic in CRUD Layer 🟡

**Problem:** Complex business logic mixed with data access.

**Evidence:**
```python
def create_model(db: Session, payload: ModelCreate) -> Model:
    model = Model(**payload.model_dump())
    db.add(model)
    db.flush()
    
    # Business logic: Auto-create compensation adjustment
    effective_date = model.start_date or date.today()
    existing_adjustment = (...)
    if not existing_adjustment:
        create_compensation_adjustment(...)  # Side effect
    
    db.commit()
    return model
```

**Should be:**
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

**Severity:** Medium

---

### Issue #6: Hardcoded Constants 🟡

**Problem:** Business constants defined at module level.

**Evidence:**
```python
# Line 29-32
ADVANCE_DEFAULT_MIN_FLOOR = Decimal("500")
ADVANCE_DEFAULT_MAX_PER_RUN = Decimal("600")
ADVANCE_DEFAULT_CAP_MULTIPLIER = Decimal("1.0")
```

**Issue:**
- Not configurable
- Scattered across different files
- No documentation of what these mean

**Better Approach:**
```python
# config/settings.py or constants.py
class AdvanceConfig:
    MIN_FLOOR = Decimal("500")
    MAX_PER_RUN = Decimal("600")
    CAP_MULTIPLIER = Decimal("1.0")
```

**Severity:** Low

---

### Issue #7: Missing Docstrings on Key Functions 🟡

**Problem:** Many functions lack documentation.

**Evidence:**
```python
# No docstring
def list_models(
    db: Session,
    code: str | None = None,
    status: str | None = None,
    ...
) -> Sequence[Model]:
    stmt = select(Model)
    ...

# Has docstring (good)
def get_paid_payouts_for_model(db: Session, model_id: int) -> Sequence[Payout]:
    """
    Get all paid payouts for a model, sorted by pay date descending.
    This is the unified source of truth for payment history.
    """
```

**Severity:** Low

---

### Issue #8: Inline Import 🟡

**Problem:** Import statement in middle of file.

**Evidence:**
```python
# Line 1014
from typing import Any  # Late import
```

**Impact:**
- Unexpected import location
- Breaks convention (all imports at top)

**Severity:** Low

---

### Issue #9: N+1 Query Risk in Loops 🔴

**Problem:** Potential performance issues in loops.

**Evidence:**
```python
# cleanup_empty_runs - N+1 query pattern
def cleanup_empty_runs(db: Session) -> dict:
    runs = db.execute(select(ScheduleRun.id)).scalars().all()
    for run_id in runs:
        count = db.execute(  # Query per iteration!
            select(func.count()).where(Payout.schedule_run_id == run_id)
        ).scalar_one() or 0
        ...
```

**Better Approach:**
```python
# Single query with aggregation
def cleanup_empty_runs(db: Session) -> dict:
    # Get counts for all runs in one query
    run_counts = db.execute(
        select(ScheduleRun.id, func.count(Payout.id))
        .outerjoin(Payout)
        .group_by(ScheduleRun.id)
    ).all()
    
    empty_run_ids = [rid for rid, count in run_counts if count == 0]
    # Delete empty runs in batch
```

**Severity:** Medium-High (for larger datasets)

---

### Issue #10: Complex Nested Logic in _apply_advance_allocations_for_run 🔴

**Problem:** Lines 1378-1455 (77 lines) with deep nesting.

**Evidence:**
```python
def _apply_advance_allocations_for_run(db, run, payouts):
    by_model: dict[int, list[Payout]] = {}
    for p in payouts:
        if not p.model_id:
            continue
        by_model.setdefault(p.model_id, []).append(p)
    
    for model_id, rows in by_model.items():
        rows.sort(...)
        advances = list(...)
        if not advances:
            continue
        temp_remaining = {...}
        
        for payout in rows:
            available = ...
            if available <= 0:
                continue
            total_deducted = Decimal("0")
            
            for adv in advances:  # Triple nested loop!
                if temp_remaining[adv.id] <= 0:
                    continue
                # Strategy calculation
                if (adv.strategy or "fixed") == "fixed":
                    ...
                else:
                    ...
                # More logic...
                if planned <= 0:
                    continue
                # Allocation creation
                ...
                if (...):
                    break
        db.flush()
```

**Impact:**
- Hard to understand flow
- Difficult to test edge cases
- Bug-prone

**Severity:** High

---

## 3. Refactoring Recommendations

### Recommendation #1: Split by Domain

Split `crud.py` into domain-specific modules:

```
app/
├── crud/
│   ├── __init__.py      # Re-export all for backward compat
│   ├── models.py        # Model CRUD (~200 lines)
│   ├── payouts.py       # Payout CRUD (~200 lines)
│   ├── schedules.py     # Schedule CRUD (~200 lines)
│   ├── advances.py      # Advance CRUD (~300 lines)
│   ├── adhoc.py         # Ad-hoc payments (~150 lines)
│   ├── dashboard.py     # Dashboard queries (~200 lines)
│   └── admin.py         # Admin/maintenance (~150 lines)
```

**Backward Compatibility:**
```python
# app/crud/__init__.py
from app.crud.models import *
from app.crud.payouts import *
from app.crud.schedules import *
# ... existing imports still work
```

**Effort:** Medium (4-8 hours)  
**Impact:** High

---

### Recommendation #2: Extract Dashboard Service

Create a dedicated dashboard service:

```python
# app/services/dashboard.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class DashboardMetrics:
    total_models: int
    active_models: int
    lifetime_paid: Decimal
    monthly_burn: Decimal
    # ...

class DashboardService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_model_counts(self) -> dict:
        """Get model counts by status."""
        ...
    
    def get_payout_metrics(self) -> dict:
        """Get payout aggregations."""
        ...
    
    def get_summary(self) -> DashboardMetrics:
        """Combine all metrics into summary."""
        return DashboardMetrics(
            **self.get_model_counts(),
            **self.get_payout_metrics(),
        )
```

**Effort:** Medium (2-4 hours)  
**Impact:** High

---

### Recommendation #3: Create Base CRUD Class

Reduce duplication with a generic base:

```python
# app/crud/base.py
from typing import TypeVar, Generic, Type
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")
CreateType = TypeVar("CreateType")
UpdateType = TypeVar("UpdateType")

class CRUDBase(Generic[ModelType, CreateType, UpdateType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: int) -> ModelType | None:
        return db.get(self.model, id)
    
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: CreateType) -> ModelType:
        obj = self.model(**obj_in.model_dump())
        db.add(obj)
        db.flush()
        return obj


# Usage
class CRUDModel(CRUDBase[Model, ModelCreate, ModelUpdate]):
    def get_by_code(self, db: Session, code: str) -> Model | None:
        return db.query(Model).filter(Model.code == code).first()

model_crud = CRUDModel(Model)
```

**Effort:** High (8-16 hours)  
**Impact:** Medium-High

---

### Recommendation #4: Optimize N+1 Queries

Fix the cleanup_empty_runs and similar patterns:

```python
# Before (N+1)
def cleanup_empty_runs(db):
    runs = db.execute(select(ScheduleRun.id)).scalars().all()
    for run_id in runs:
        count = db.execute(...).scalar_one()  # N queries

# After (1 query)
def cleanup_empty_runs(db):
    # Subquery for payout counts
    payout_counts = (
        select(Payout.schedule_run_id, func.count().label('cnt'))
        .group_by(Payout.schedule_run_id)
        .subquery()
    )
    
    # Outer join to find runs with 0 payouts
    empty_runs = db.execute(
        select(ScheduleRun.id)
        .outerjoin(payout_counts, ScheduleRun.id == payout_counts.c.schedule_run_id)
        .where(func.coalesce(payout_counts.c.cnt, 0) == 0)
    ).scalars().all()
    
    # Batch delete
    if empty_runs:
        db.query(ScheduleRun).filter(ScheduleRun.id.in_(empty_runs)).delete()
```

**Effort:** Low-Medium (1-2 hours per function)  
**Impact:** High (performance)

---

### Recommendation #5: Extract Advance Allocation Logic

Simplify the complex allocation function:

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
    
    def calculate_allocation(
        self, advance: ModelAdvance, gross_amount: Decimal
    ) -> Decimal:
        """Calculate allocation amount based on strategy."""
        if advance.strategy == "fixed":
            return min(advance.fixed_amount, advance.amount_remaining)
        else:
            pct = advance.percent_rate / Decimal("100")
            return min(gross_amount * pct, advance.amount_remaining)
    
    def plan_allocations(
        self, payouts: list[Payout], advances: list[ModelAdvance]
    ) -> list[AllocationPlan]:
        """Generate allocation plan without side effects."""
        plans = []
        # Pure calculation logic
        ...
        return plans
    
    def apply_allocations(
        self, run: ScheduleRun, payouts: list[Payout]
    ) -> None:
        """Apply allocations to payouts and create records."""
        plans = self.plan_allocations(...)
        for plan in plans:
            # Apply to payout
            # Create allocation record
            ...
```

**Effort:** Medium (4-6 hours)  
**Impact:** High (maintainability)

---

## 4. Priority Matrix

| Recommendation | Impact | Effort | Priority |
|----------------|--------|--------|----------|
| Split by domain | High | Medium | 🔴 P1 |
| Extract dashboard service | High | Medium | 🔴 P1 |
| Optimize N+1 queries | High | Low | 🔴 P1 |
| Extract advance allocation | High | Medium | 🟡 P2 |
| Create base CRUD class | Medium | High | 🟡 P2 |
| Add missing docstrings | Low | Low | 🟢 P3 |
| Move inline import | Low | Low | 🟢 P3 |
| Centralize constants | Low | Low | 🟢 P3 |

---

## 5. Implementation Plan

### Phase 1: Quick Wins (Day 1)

1. Move inline import to top
2. Add docstrings to key functions
3. Fix N+1 in cleanup_empty_runs

### Phase 2: Split (Days 2-3)

1. Create `app/crud/` directory
2. Move model functions to `crud/models.py`
3. Move payout functions to `crud/payouts.py`
4. Create `__init__.py` for backward compatibility
5. Update imports throughout app

### Phase 3: Refactor Dashboard (Day 4)

1. Create `services/dashboard.py`
2. Break `dashboard_summary` into smaller functions
3. Add caching if needed

### Phase 4: Advance Logic (Day 5)

1. Create `services/advance_allocator.py`
2. Extract and simplify allocation logic
3. Add comprehensive tests

---

## 6. Conclusion

`crud.py` is functional but has accumulated technical debt typical of a fast-growing project. The main issues are:

1. **Size** - Too many responsibilities in one file
2. **Complexity** - Some functions are too long
3. **Performance** - N+1 query patterns
4. **Testability** - Monolithic structure is hard to test

The recommended approach is to:
1. Split by domain (highest impact)
2. Extract complex logic to services
3. Optimize queries
4. Add tests during refactoring

**Estimated Total Effort:** 20-40 hours  
**Expected Improvement:** 
- 40-50% reduction in file sizes
- Improved testability
- Better performance on dashboard
- Easier onboarding for new developers

---

*Analysis completed December 24, 2025*
