# Task List

---

## 📖 How to Use This File

### Purpose
Track pending tasks, completed work, and project roadmap for PayrollDesk.

### Document Structure

| Section | Purpose |
|---------|---------|
| **Completed This Session** | Recently finished work (reverse chronological by date) |
| **Remaining Backlog** | Pending tasks by priority (High → Medium → Low) |
| **Session Summary** | Current stats (branch, commits, version, tests) |

### Task Format

Use tables with consistent columns:

```markdown
| Task | Category | Effort | Status |
|------|----------|--------|--------|
| Implement feature X | API | Medium | ✅ Done |
```

**Effort Levels:**
- **Low** - Under 1 hour
- **Medium** - 1-4 hours  
- **High** - 4+ hours

**Status Icons:**
- (blank) = Not started
- ⏳ = In progress
- ✅ = Done

### When to Update

| Trigger | Action |
|---------|--------|
| Starting work on a task | Mark as ⏳ In Progress |
| Completing a task | Mark as ✅ Done, add completion date |
| New requirement identified | Add to appropriate priority level |
| End of work session | Update Session Summary stats |
| Version bump | Update version in Session Summary |

### Housekeeping Rules

1. **Archive old completed tasks** - After 2+ weeks, move "Completed This Session" entries to CHANGELOG.md to keep this file lean
2. **Review Low Priority quarterly** - Delete tasks that are no longer relevant or have been superseded
3. **Consolidate duplicates** - Merge similar tasks into single items with combined scope
4. **Re-evaluate effort** - Update estimates after learning more about a task's complexity
5. **Session reset** - At start of major new work phase, archive completed items
6. **Keep versions in sync** - Session Summary version must match `app/__init__.py`

### Cross-References

- **CHANGELOG.md** - Permanent history of all changes (archive destination)
- **DOCUMENTATION_GUIDE.md** - When to update which documentation files
- **app/__init__.py** - Source of truth for version number

---

## Completed This Session

### ✅ Performance Optimizations (2024-12-24)

| Task | Category | Details |
|------|----------|---------|
| Fix N+1 in cleanup_empty_runs | Database | Batch query with subquery |
| Add dashboard caching | Performance | 5-min TTL, auto-invalidation |
| Add eager loading option | CRUD | list_schedule_runs(eager_load_payouts=True) |
| Configurable pool settings | Database | DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE |
| Add payout indexes | Database | 4 new indexes + migration |

### ✅ Test Coverage & Quality (v2.32.0 → v2.32.1)

| Achievement | Details |
|-------------|---------|
| CRUD test coverage | 86% on crud.py (was 75%) |
| Total tests | 194 tests (was 118) |
| Integration tests | 14 workflow tests |
| Error scenario tests | 20 validation tests |

> **Note:** Detailed per-version changes in CHANGELOG.md (v2.27.0 → v2.32.1)

---

## Remaining Backlog

### High Priority

*All completed ✅*

### Medium Priority

*All completed ✅*

### Low Priority (Future Enhancements)

| Task | Category | Effort | Notes |
|------|----------|--------|-------|
| Background tasks for exports | Performance | Medium | FastAPI BackgroundTasks |
| Consider async SQLAlchemy | Performance | High | Only if concurrent load increases |
| Add full-text search | CRUD | High | Requires PostgreSQL tsvector |
| Implement Redis caching | Performance | High | New infrastructure dependency |
| Add API versioning | API | Medium | Only if external API consumers |

### UI/UX Improvements

| Task | Category | Effort | Priority | Notes |
|------|----------|--------|----------|-------|
| Standardize button classes | CSS | Medium | High | Unify `.btn`, `.btn--primary`, etc. |
| Extract login page styles | CSS | Low | High | Move inline styles to stylesheet |
| Audit focus indicators | A11y | Medium | High | All interactive elements need visible focus |
| Add skeleton loaders | UX | Medium | Medium | For async content (payments, dashboard) |
| Complete ARIA audit | A11y | Medium | Medium | Add missing labels to icon buttons |
| Align login page theme | CSS | Low | Low | Match purple→navy color scheme |
| Dark/Light theme toggle | UX | High | Low | System preference detection |
| Enhanced toast system | UX | Medium | Low | Auto-dismiss, animation, queue |

---

## Session Summary

**Branch:** `feature/payrolldesk-v2`  
**Current Version:** v2.32.2  
**Test Count:** 194 tests  
**Coverage:** 86% on crud.py

### Session Achievements
- ✅ All High Priority tasks completed
- ✅ All Medium Priority tasks completed
- ✅ Test coverage: 75% → 86% (+76 tests)
- ✅ Performance: N+1 fix, caching, indexes
- ✅ Configuration: Pool settings, eager loading

### Backlog Status
| Priority | Status |
|----------|--------|
| High | ✅ Complete |
| Medium | ✅ Complete |
| Low | 5 future enhancements |
| UI/UX | 8 improvements identified |

---

*Last Updated: 2025-12-24*  
*Last Housekeeping: 2025-12-24*
