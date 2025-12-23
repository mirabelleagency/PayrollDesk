# Database Data Loss Investigation

**Investigation Date:** December 24, 2025  
**Reported Issue:** Recent data loss incidents after DB operations

---

## Executive Summary

The investigation uncovered **3 critical issues** and **2 high-risk patterns** that could cause data loss:

| Issue | Severity | Impact | Status |
|-------|----------|--------|--------|
| SQLite FK enforcement OFF | 🔴 Critical | Orphaned/corrupt data | Fix Required |
| Test cleanup uses real reset function | 🔴 Critical | Could wipe shared DB | Fix Required |
| Missing session close in get_session | 🟡 High | Connection leak | Monitor |
| Silent exception swallowing | 🟡 High | Hidden failures | Fix Required |
| Confusing dev fallback | 🟢 Medium | Wrong DB connection | Documented |

---

## Issue #1: SQLite Foreign Keys NOT Enforced 🔴 CRITICAL

### Problem

SQLite **disables foreign key enforcement by default**. The production code never enables it, while the test code does.

**Test conftest.py (line 22-25):**
```python
# Enable SQLite foreign keys
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

**app/database.py:** 
```python
# ❌ NO PRAGMA foreign_keys=ON anywhere!
def _create_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)
```

### Impact

Without FK enforcement:
1. **DELETE CASCADE doesn't work** - Deleting a Model won't delete its Payouts
2. **Orphaned records** - Payouts can exist without Models
3. **Data integrity violations** - Can insert references to non-existent records
4. **Silent corruption** - No errors, just invalid data

### Evidence

The models have CASCADE delete configured:
```python
# app/models.py line 64
payouts: Mapped[list["Payout"]] = relationship(back_populates="model", cascade="all, delete-orphan")
```

But if FKs are OFF, this relies on SQLAlchemy ORM cascade ONLY, which:
- Only works when objects are loaded in session
- Doesn't work for raw SQL deletes
- Doesn't work when using `synchronize_session=False`

### Fix Required

**Add to app/database.py after line 38:**
```python
from sqlalchemy import event

def _create_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    
    # Enable foreign key enforcement for SQLite
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    return engine
```

---

## Issue #2: Test Cleanup Uses Production Reset Function 🔴 CRITICAL

### Problem

The test suite's autouse fixture calls `crud.reset_application_data()` before every test:

**conftest.py (line 43-54):**
```python
@pytest.fixture(autouse=True)
def _clean_domain_tables():
    from app import crud
    from app.database import SessionLocal
    session = SessionLocal()
    try:
        crud.reset_application_data(session)  # ⚠️ Deletes ALL production data!
    finally:
        try:
            session.close()
        except Exception:
            pass
```

### Risk Scenario

If tests accidentally run against production DB:
1. Every test deletes ALL models, payouts, schedule runs
2. User accounts are preserved but all business data is gone
3. No confirmation required (unlike the web UI)

### Evidence

`reset_application_data` deletes everything:
```python
def reset_application_data(db: Session) -> dict[str, int]:
    # Delete in dependency order to satisfy FKs across SQLite/Postgres
    deleted["payout_allocations"] = db.query(PayoutAdvanceAllocation).delete(...)
    deleted["advance_repayments"] = db.query(AdvanceRepayment).delete(...)
    deleted["model_advances"] = db.query(ModelAdvance).delete(...)
    deleted["validations"] = db.query(ValidationIssue).delete(...)
    deleted["payouts"] = db.query(Payout).delete(...)
    deleted["schedule_runs"] = db.query(ScheduleRun).delete(...)
    deleted["adjustments"] = db.query(ModelCompensationAdjustment).delete(...)
    deleted["adhoc_payments"] = db.query(AdhocPayment).delete(...)
    deleted["models"] = db.query(Model).delete(...)
    db.commit()
```

### Safeguards Needed

1. **conftest.py should verify test DB:**
```python
@pytest.fixture(autouse=True)
def _clean_domain_tables():
    from app.database import DATABASE_URL, SessionLocal
    
    # Safety: never run against production URLs
    if "render.com" in DATABASE_URL or "postgres" in DATABASE_URL.lower():
        pytest.skip("Refusing to run tests against production database")
    
    # ... rest of cleanup
```

2. **reset_application_data should check environment:**
```python
def reset_application_data(db: Session, force: bool = False) -> dict[str, int]:
    env = os.getenv("ENVIRONMENT", "production")
    if env not in ("test", "development") and not force:
        raise RuntimeError("reset_application_data blocked in production mode")
    # ... rest of function
```

---

## Issue #3: Silent Exception Swallowing 🟡 HIGH

### Problem

Many operations catch exceptions and pass silently, hiding potential data loss:

**app/routers/admin.py (multiple locations):**
```python
try:
    crud.log_admin_action(db, admin.id, "purge_model", {"impact": impact})
except Exception:
    # Logging should not block the action
    pass  # ❌ Silent failure - no log, no trace
```

**app/routers/admin.py line 359:**
```python
result = crud.reset_application_data(db)
try:
    crud.log_admin_action(db, admin.id, "reset_application_data", result)
except Exception:
    pass  # ❌ Reset happened but not logged!
```

### Impact

- Admin actions complete but aren't logged
- No audit trail when things go wrong
- User doesn't know if operation succeeded partially

### Fix

At minimum, log the exception:
```python
try:
    crud.log_admin_action(db, admin.id, "reset_application_data", result)
except Exception as exc:
    print(f"[WARNING] Failed to log admin action: {exc}")
    # Or use proper logging module
```

---

## Issue #4: Dev Fallback Can Switch Databases Unexpectedly 🟢 MEDIUM

### Problem

The database connection can silently switch from PostgreSQL to SQLite if the PG connection fails:

**app/database.py (line 54-66):**
```python
try:
    engine = _create_engine(DATABASE_URL)
    with engine.connect() as _conn:
        pass
except Exception as e:
    env = os.getenv("ENVIRONMENT", "production").lower()
    default_fallback_flag = "true" if env in ("development", "dev", "local") else "false"
    allow_dev_fallback = os.getenv("LOCAL_DEV_SQLITE_FALLBACK", default_fallback_flag).lower()
    
    if env in ("development", "dev", "local") and allow_dev_fallback:
        # Use local SQLite for development
        fallback = f"sqlite:///{DEFAULT_SQLITE_PATH}"
        print(f"[database] Falling back to SQLite (dev-only) at {fallback}")
        DATABASE_URL = fallback  # ⚠️ Now using different database!
```

### Risk Scenario

1. User is on "development" environment
2. PostgreSQL is temporarily down
3. App silently switches to SQLite
4. User adds data to SQLite
5. PostgreSQL comes back, app restarts
6. Now connected to PostgreSQL which doesn't have the new data
7. **User thinks data was lost**

### Current Safeguard

The console log shows the fallback, but users often don't check logs:
```
[database] Could not connect to database at 'postgresql://...'
[database] Falling back to SQLite (dev-only) at sqlite:///data/payroll.db
```

### Improvement

Add a clear visual indicator in the UI when running on SQLite fallback mode.

---

## Issue #5: No Database Backups Before Reset 🟡 HIGH

### Problem

The `reset_application_data` function has no backup mechanism:

```python
def reset_application_data(db: Session) -> dict[str, int]:
    # Directly deletes without creating any backup
    deleted["models"] = db.query(Model).delete(synchronize_session=False)
    db.commit()  # Point of no return
```

### Impact

- One accidental click on "Reset Application Data" and everything is gone
- Even with confirmation prompt, mistakes happen
- No way to recover without external database backup

### Recommendations

1. **Create snapshot before reset:**
```python
def reset_application_data(db: Session) -> dict[str, int]:
    # Create emergency snapshot first
    snapshot_path = Path(f"data/backups/pre_reset_{datetime.now().isoformat()}.json")
    _export_all_data(db, snapshot_path)
    
    # Then proceed with reset
    ...
```

2. **Implement soft-delete for critical operations:**
```python
# Add deleted_at column, set it instead of deleting
model.deleted_at = datetime.now()
# Actual deletion in background job after 30 days
```

---

## Other Observations

### Transaction Patterns

The codebase uses `autoflush=False, autocommit=False` which is correct:
```python
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

However, there's inconsistency in when `db.commit()` is called:
- Some CRUD functions call `db.commit()` themselves
- Some leave it to the caller
- This can cause confusion about when data is actually persisted

### Missing Session Close in Exception Paths

Some code paths may not properly close sessions on errors:
```python
# conftest.py - good pattern
finally:
    try:
        session.close()
    except Exception:
        pass

# Some routes - might leak on exceptions
session = SessionLocal()
# ... operations without try/finally
```

---

## Priority Fixes

### Immediate (P0)

1. **Add PRAGMA foreign_keys=ON** to app/database.py
   - Without this, data integrity is not enforced
   - ~5 lines of code

2. **Add production safety check** to reset_application_data
   - Prevent accidental wipes
   - ~10 lines of code

### Short-term (P1)

3. **Add environment check to conftest.py**
   - Prevent tests from running against prod
   - ~5 lines of code

4. **Replace silent exception passes with logging**
   - Multiple locations in admin.py
   - ~20 lines of code

### Medium-term (P2)

5. **Add pre-reset backup mechanism**
   - Export to JSON before destructive operations
   - ~50 lines of code

6. **Add visual indicator for SQLite fallback mode**
   - Show banner in UI when not on primary DB
   - ~30 lines of code

---

## Verification Steps

After applying fixes, verify:

```bash
# 1. Check if foreign keys are enabled
sqlite3 data/payroll.db "PRAGMA foreign_keys"
# Should return: 1

# 2. Try to delete a model with payouts
# Should cascade delete payouts automatically

# 3. Try to run tests against prod URL
# Should fail/skip with clear message

# 4. Check admin action logs after reset
# Should see logged entry
```

---

## Appendix: Related Code Locations

| File | Lines | Description |
|------|-------|-------------|
| app/database.py | 37-40 | Engine creation (needs FK fix) |
| app/crud.py | 1482-1534 | reset_application_data |
| conftest.py | 43-54 | Test cleanup fixture |
| app/routers/admin.py | 343-368 | Reset endpoint |
| app/routers/admin.py | 270-290 | Purge endpoint |

---

*Investigation completed December 24, 2025*
