# Task List

## Current Sprint: Database Layer Cleanup

### Context
After setting up Alembic migrations, the `app/database.py` file contains 180+ lines of legacy manual migration code (`ensure_schema_updates()`) that is now redundant. This task removes that technical debt while preserving essential functionality.

### Assessment Summary
- **File:** `app/database.py` (332 lines)
- **Rating:** 6.5/10
- **Main Issue:** Massive `ensure_schema_updates()` function with raw SQL migrations
- **Impact:** Runs on every startup, duplicates Alembic functionality

---

## Task Checklist: database.py Refactor

### Pre-Refactor Verification
- [ ] Confirm Alembic is configured and baseline migration exists
- [ ] Verify all production/staging databases have required columns
- [ ] Run test suite to establish baseline (46 tests passing)

### Phase 1: Remove Legacy Migration Code
- [ ] Delete `ensure_schema_updates()` function (~180 lines)
- [ ] Remove call to `ensure_schema_updates()` from `init_db()`
- [ ] Remove unused imports (`date` from datetime, `inspect` if no longer needed)
- [ ] Clean up `init_db()` to be minimal

### Phase 2: Improve Code Quality
- [ ] Replace `print()` statements with proper logging
- [ ] Add connection pool configuration for PostgreSQL
- [ ] Fix bare `except:` clauses to catch specific exceptions
- [ ] Move module-level side effects into functions

### Phase 3: Testing & Validation
- [ ] Run full test suite
- [ ] Verify app starts correctly with SQLite
- [ ] Verify app starts correctly with PostgreSQL
- [ ] Verify Alembic migrations still work

### Phase 4: Documentation
- [ ] Update CHANGELOG.md
- [ ] Add inline comments explaining remaining code
- [ ] Update MIGRATIONS.md if needed

---

## What We're About to Do

### Goal
Reduce `database.py` from 332 lines to ~100 lines by removing the legacy `ensure_schema_updates()` function that manually applies schema changes via raw SQL.

### Why It's Safe Now
1. ✅ Alembic is configured (added this session)
2. ✅ Baseline migration exists (`0001_initial_baseline.py`)
3. ✅ All databases already have the required columns (the function has run)
4. ✅ Future schema changes will use proper Alembic migrations

### Changes Summary

| Component | Before | After |
|-----------|--------|-------|
| `ensure_schema_updates()` | 180+ lines raw SQL | Deleted |
| `init_db()` | Calls ensure_schema_updates | Just creates tables + admin |
| Print statements | 15+ print() calls | Proper logging |
| File length | 332 lines | ~100 lines |
| Connection pooling | Default | Configured |

### Risk Mitigation
- Keep `init_db()` to auto-create tables for fresh databases
- Keep `_enable_sqlite_foreign_keys()` for SQLite FK enforcement
- All schema changes going forward use Alembic

### Expected Outcome
- Cleaner, more maintainable database configuration
- Single source of truth for migrations (Alembic)
- Better logging for debugging
- Faster app startup (no schema inspection on every boot)

---

## Future Tasks (Backlog)

### From database.py Assessment
- [ ] Add database health check endpoint
- [ ] Implement connection retry logic
- [ ] Add query timing/logging for debugging
- [ ] Consider async SQLAlchemy for FastAPI

### From Full System Assessment
- [ ] Add CommissionPayout CRUD operations
- [ ] Add bulk payout status update
- [ ] Improve test coverage for crud.py
- [ ] Add soft delete to Model

---

*Last Updated: 2024-12-24*
*Sprint: PayrollDesk V2 Cleanup*
