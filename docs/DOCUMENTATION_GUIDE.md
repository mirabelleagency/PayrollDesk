# PayrollDesk Documentation Guide

> Instructions for AI agents and developers to maintain project documentation consistently.

---

## 📋 Table of Contents

1. [Purpose](#purpose)
2. [When to Update Documentation](#when-to-update-documentation)
3. [What to Update](#what-to-update)
4. [Documentation Files Reference](#documentation-files-reference)
5. [Version Numbering](#version-numbering)
6. [Changelog Management](#changelog-management)
7. [README Updates](#readme-updates)
8. [Commit Message Format](#commit-message-format)
9. [Branch Naming Conventions](#branch-naming-conventions)
10. [Release Checklist](#release-checklist)
11. [Execute Documentation Guide](#execute-documentation-guide)
12. [Database & Migration Docs](#database--migration-docs)
13. [Environment Configuration](#environment-configuration)
14. [Code Documentation Standards](#code-documentation-standards)
15. [API Documentation](#api-documentation)
16. [Error Codes & Messages](#error-codes--messages)
17. [Security Documentation](#security-documentation)
18. [TODO.md Management](#todomd-management)
19. [Testing Documentation](#testing-documentation)
20. [Deprecation Process](#deprecation-process)
21. [Troubleshooting Documentation](#troubleshooting-documentation)

---

## Purpose

This guide provides instructions for maintaining PayrollDesk project documentation. **Refer to this document whenever updating any project documentation.**

**Who should use this:**
- AI agents (Copilot) working on the project
- Developers contributing to the codebase
- Anyone making changes that require documentation updates

---

## When to Update Documentation

Update documentation when:

| Trigger | What to Update |
|---------|----------------|
| **New feature added** | CHANGELOG, README (if user-facing), version bump |
| **Bug fixed** | CHANGELOG |
| **Breaking change** | CHANGELOG, MIGRATION_GUIDE, version bump (major) |
| **API endpoint changed** | CHANGELOG, TECHNICAL_SPEC (API section) |
| **Database schema changed** | MIGRATION_GUIDE, TECHNICAL_SPEC (schema section) |
| **Configuration changed** | README, TECHNICAL_SPEC (config section), .env.example |
| **Dependency added/removed** | requirements.txt, CHANGELOG |
| **Security fix** | CHANGELOG (mark as security) |
| **Deprecation** | CHANGELOG, mark deprecated in code |
| **New router/module added** | TECHNICAL_SPEC (architecture, file structure) |
| **Architecture change** | TECHNICAL_SPEC (architecture section) |

---

## What to Update

### Decision Matrix

```
┌─────────────────────────┬──────────┬───────────┬─────────┬──────────┬──────────────┐
│ Change Type             │ CHANGELOG│ README    │ Version │ Migration│ TECHNICAL_SPEC│
├─────────────────────────┼──────────┼───────────┼─────────┼──────────┼──────────────┤
│ New feature             │ ✅       │ If visible│ Minor++ │ ❌       │ If structural │
│ Bug fix                 │ ✅       │ ❌        │ Patch++ │ ❌       │ ❌           │
│ Breaking change         │ ✅       │ ✅        │ Major++ │ ✅       │ ✅           │
│ Performance improvement │ ✅       │ ❌        │ Patch++ │ ❌       │ ❌           │
│ Security fix            │ ✅       │ ❌        │ Patch++ │ ❌       │ If auth flow  │
│ Documentation only      │ ❌       │ ❌        │ ❌      │ ❌       │ ❌           │
│ Database migration      │ ✅       │ ❌        │ Minor++ │ ✅       │ ✅ (schema)   │
│ Dependency update       │ ✅       │ ❌        │ Patch++ │ ❌       │ If major      │
│ New API endpoint        │ ✅       │ ❌        │ Minor++ │ ❌       │ ✅ (API ref)  │
│ New env variable        │ ✅       │ ✅        │ ❌      │ ❌       │ ✅ (config)   │
└─────────────────────────┴──────────┴───────────┴─────────┴──────────┴──────────────┘
```

---

## Documentation Files Reference

| File | Purpose | Location |
|------|---------|----------|
| `README.md` | Project overview, setup instructions | Root |
| `CHANGELOG.md` | Version history, release notes | Root |
| `TECHNICAL_SPEC.md` | System architecture, database schema, API reference | docs/ |
| `UI_UX_GUIDE.md` | User interface design, components, workflows | docs/ |
| `MIGRATION_GUIDE.md` | Database migration instructions | Root |
| `MIGRATION_README.md` | Alembic migration details | Root |
| `TODO.md` | Pending tasks and roadmap | Root |
| `DUPLICATE_HANDLING.md` | Duplicate detection logic docs | Root |
| `DOCUMENTATION_GUIDE.md` | This guide - documentation standards | docs/ |
| `tasksync.md` | TaskSync protocol for AI agents | docs/ |
| `app/__init__.py` | Version number (`__version__`) | app/ |
| `.env.example` | Environment variable template | Root (if exists) |
| `requirements.txt` | Python dependencies | Root |

---

## Version Numbering

**Follow Semantic Versioning (SemVer):** `MAJOR.MINOR.PATCH`

| Version Part | When to Increment | Example |
|--------------|-------------------|---------|
| **MAJOR** | Breaking changes, incompatible API changes | 1.0.0 → 2.0.0 |
| **MINOR** | New features (backward compatible) | 1.0.0 → 1.1.0 |
| **PATCH** | Bug fixes, minor improvements | 1.0.0 → 1.0.1 |

### Version Location

Update version in `app/__init__.py`:

```python
__version__ = "X.Y.Z"
```

### Version Bump Commands

```bash
# After updating __init__.py, verify:
python -c "from app import __version__; print(__version__)"
```

---

## Changelog Management

### In-App Changelog Synchronization

The application displays the changelog at `/changelog` by reading directly from `CHANGELOG.md` in the project root. There is **no separate in-app changelog** to maintain - the same file is used everywhere.

**Important:** Any changes to `CHANGELOG.md` are immediately visible in the app when the page is refreshed.

### Version Synchronization Checklist

When releasing a new version, ensure these are in sync:

| Location | What to Update |
|----------|----------------|
| `app/__init__.py` | `__version__ = "X.Y.Z"` |
| `CHANGELOG.md` | New version entry at the top |
| `docs/TECHNICAL_SPEC.md` | Version number at top of document |

**Verification:**
```bash
# Check app version
python -c "from app import __version__; print(__version__)"

# Check changelog has matching version
head -10 CHANGELOG.md
```

### Format

Use [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description

### Deprecated
- Feature being phased out

### Removed
- Removed feature

### Security
- Security fix description
```

### Categories (in order)

1. **Added** - New features
2. **Changed** - Changes to existing functionality
3. **Deprecated** - Soon-to-be removed features
4. **Removed** - Removed features
5. **Fixed** - Bug fixes
6. **Security** - Vulnerability fixes

### Rules

- Most recent version at the TOP
- Use present tense ("Add feature" not "Added feature")
- Include issue/PR references if applicable
- Be concise but descriptive
- Group related changes
- **Use correct year in dates** (common mistake: typing previous year)

### Date Format

Always use `YYYY-MM-DD` format with the **correct current year**:
- ✅ `## v2.32.2 - 2025-12-24`
- ❌ `## v2.32.2 - 2024-12-24` (wrong year)
- ❌ `## v2.32.2 - 12/24/2025` (wrong format)

### Example Entry

```markdown
## v1.5.0 - 2025-12-24

### Added
- Add "Add New Models" button to safely include new models in existing schedule
- Add safe refresh functionality that preserves existing payout data

### Fixed
- Fix data loss issue when viewing current month's schedule (#123)
- Remove auto-refresh that was wiping payout updates

### Changed
- Schedule view no longer auto-refreshes on page load
```

---

## README Updates

Update README.md when:

- Setup instructions change
- New environment variables added
- New features visible to end users
- Deployment process changes
- Dependencies change significantly

### Sections to Maintain

- Features list
- Installation/setup steps
- Environment variables table
- Usage instructions
- Troubleshooting

---

## Technical Specification Updates

The `docs/TECHNICAL_SPEC.md` document contains comprehensive technical documentation. Update it when:

### When to Update

| Change Type | Update Section |
|-------------|----------------|
| New database table | Database Schema (add table diagram, column details) |
| New column added | Database Schema (update table details) |
| New index/constraint | Database Schema (update constraints/indexes) |
| New API endpoint | API Reference (add to appropriate router table) |
| New router added | API Reference (add new router section) |
| Environment variable | Configuration (add to env vars table) |
| Architecture change | Architecture (update diagrams) |
| New business logic | Core Business Logic (document flow) |
| Authentication change | Authentication & Security section |
| New file/module | File Structure (update tree) |

### Sections Reference

1. **System Overview** - Feature list, key capabilities
2. **Architecture** - Layer diagram, component responsibilities
3. **Technology Stack** - Backend/frontend/testing tools
4. **Database Schema** - ER diagram, table definitions, constraints
5. **API Reference** - All endpoints by router
6. **Authentication & Security** - Session management, lockout, hashing
7. **Core Business Logic** - Payroll calculation, advances, commissions
8. **Data Flow Diagrams** - Process flows
9. **Configuration** - Environment variables
10. **File Structure** - Directory tree, file sizes

### Update Process

1. Make code changes
2. Update relevant TECHNICAL_SPEC.md section(s)
3. Update version number at top of file
4. Update "Last Updated" date
5. Commit together: `docs: update technical spec for [change]`

---

## Commit Message Format

Use **Conventional Commits** format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style (formatting, no logic change) |
| `refactor` | Code refactoring |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |
| `build` | Build system changes |

### Examples

```bash
feat(schedules): add safe refresh button for adding new models
fix(payouts): prevent data loss on schedule view auto-refresh
docs: update changelog for v1.5.0 release
chore: bump version to 1.5.0
```

### Rules

- Use imperative mood ("add" not "added")
- First line max 72 characters
- Reference issues: `fix(auth): resolve login timeout (#45)`
- Breaking changes: add `BREAKING CHANGE:` in footer

---

## Branch Naming Conventions

| Branch Type | Format | Example |
|-------------|--------|---------|
| Feature | `feature/<name>` | `feature/payrolldesk-v2` |
| Bug fix | `fix/<name>` | `fix/schedule-data-loss` |
| Hotfix | `hotfix/<name>` | `hotfix/critical-auth-bug` |
| Release | `release/<version>` | `release/1.5.0` |
| Documentation | `docs/<name>` | `docs/api-reference` |

---

## Release Checklist

Before releasing a new version:

- [ ] All tests passing
- [ ] Version bumped in `app/__init__.py`
- [ ] CHANGELOG.md updated with new version section
- [ ] README.md updated (if needed)
- [ ] MIGRATION_GUIDE.md updated (if DB changes)
- [ ] Code reviewed and approved
- [ ] Branch merged to staging
- [ ] Staging tested
- [ ] Tagged release created

### Release Commands

```bash
# 1. Ensure you're on the release branch
git checkout staging

# 2. Create a git tag
git tag -a v1.5.0 -m "Release v1.5.0"

# 3. Push tag
git push origin v1.5.0
```

---

## Execute Documentation Guide

When asked to "execute documentation guide", perform this comprehensive documentation update workflow:

### Step 1: Version Verification

```bash
# Check current app version
python -c "from app import __version__; print(__version__)"

# Check CHANGELOG has matching version
head -10 CHANGELOG.md

# Check TECHNICAL_SPEC version matches
head -10 docs/TECHNICAL_SPEC.md
```

### Step 2: Review Recent Changes

```bash
# List recent commits since last documented version
git log --oneline -15

# Check for uncommitted changes
git status
```

### Step 3: Determine Version Bump Need

Use the [Decision Matrix](#what-to-update) to determine if changes warrant a version bump:

| If Changes Include | Version Action |
|-------------------|----------------|
| New feature (UI, API, etc.) | Bump MINOR (x.Y.z → x.Y+1.0) |
| Bug fixes only | Bump PATCH (x.y.Z → x.y.Z+1) |
| Breaking changes | Bump MAJOR (X.y.z → X+1.0.0) |
| Documentation only | No version change |

### Step 4: Update Documentation Files

If version bump needed:

1. **app/__init__.py** - Update `__version__`
2. **CHANGELOG.md** - Add new version section with changes
3. **docs/TECHNICAL_SPEC.md** - Update version at top
4. **docs/TODO.md** - Update version in Session Summary

### Step 5: TODO.md Housekeeping

Perform housekeeping per the [TODO.md Housekeeping](#todomd-housekeeping) section:

- [ ] Archive completed tasks older than 2 weeks
- [ ] Move detailed task info to CHANGELOG reference
- [ ] Fix any date typos (common: wrong year)
- [ ] Update "Completed This Session" with current work
- [ ] Remove completed tasks from backlog tables
- [ ] Update "Backlog Status" counts
- [ ] Verify "Last Updated" and "Last Housekeeping" dates

### Step 6: Verify and Commit

```bash
# Run tests to verify nothing broke
python -m pytest tests/ -q

# Stage and review changes
git add -A
git status
git diff --cached --stat

# Commit with appropriate message
git commit -m "chore(release): vX.Y.Z - brief description"
```

### Complete Checklist

```markdown
□ Version verified in app/__init__.py
□ CHANGELOG.md has entry for new version
□ TECHNICAL_SPEC.md version updated
□ TODO.md version updated
□ TODO.md housekeeping performed
□ All tests passing
□ Changes committed
```

---

## Database & Migration Docs

When database schema changes:

1. **Update MIGRATION_GUIDE.md** with:
   - What changed
   - Alembic migration command
   - Rollback instructions
   - Data migration notes (if any)

2. **Document in CHANGELOG** under "Changed" or "Added"

3. **Update models documentation** in code docstrings

### Migration Entry Example

```markdown
### Migration: Add PayoutAdvanceAllocation Table

**Version:** 1.4.0  
**Date:** 2024-12-20

**Forward:**
```bash
alembic upgrade head
```

**Rollback:**
```bash
alembic downgrade -1
```

**Notes:**
- New table for tracking advance allocations
- No data migration required
```

---

## Environment Configuration

When adding new environment variables:

1. **Update `.env.example`** (if exists)
2. **Update README.md** environment section
3. **Add to CHANGELOG** if user-facing

### Environment Variable Documentation Format

```markdown
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `SECRET_KEY` | Yes | - | JWT signing key |
| `DEBUG` | No | `false` | Enable debug mode |
```

---

## Code Documentation Standards

### Python Docstrings

Use Google-style docstrings:

```python
def process_payroll(db: Session, year: int, month: int) -> dict:
    """Process payroll for a given month.
    
    Args:
        db: Database session
        year: Target year (e.g., 2024)
        month: Target month (1-12)
    
    Returns:
        dict: Summary with keys 'total_amount', 'model_count'
    
    Raises:
        ValueError: If month is not 1-12
    """
```

### When to Add Docstrings

- All public functions/methods
- All classes
- Complex private functions
- Module-level documentation

---

## API Documentation

### When to Document APIs

- New endpoint added
- Endpoint behavior changed
- Request/response schema modified
- Authentication requirements changed

### Endpoint Documentation Format

Document each endpoint with:

```markdown
### POST /api/v1/schedules/{run_id}/add-new-models

**Description:** Add payouts for models not yet in the schedule.

**Authentication:** Required (Admin only)

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | Schedule run ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "added_count": 3,
  "added_codes": ["MOD001", "MOD002", "MOD003"],
  "message": "Added 3 new model(s) to schedule"
}
```

**Error Responses:**
| Code | Description |
|------|-------------|
| 404 | Schedule run not found |
| 403 | Not authorized (admin required) |
| 500 | Server error |
```

### API Versioning

- Use URL versioning: `/api/v1/`, `/api/v2/`
- Document breaking changes in CHANGELOG
- Maintain backward compatibility when possible

---

## Error Codes & Messages

### Standard Error Format

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "field": "field_name"  // optional, for validation errors
}
```

### Error Code Categories

| Code Prefix | Category | Example |
|-------------|----------|---------|
| `AUTH_` | Authentication | `AUTH_INVALID_TOKEN` |
| `VAL_` | Validation | `VAL_INVALID_DATE` |
| `NOT_` | Not Found | `NOT_FOUND_MODEL` |
| `PERM_` | Permission | `PERM_ADMIN_REQUIRED` |
| `DB_` | Database | `DB_CONNECTION_FAILED` |
| `BIZ_` | Business Logic | `BIZ_DUPLICATE_PAYOUT` |

### Adding New Error Codes

1. Add constant to error definitions (if centralized)
2. Use consistent naming: `CATEGORY_SPECIFIC_ERROR`
3. Include human-readable message
4. Document in error reference

### Error Documentation Template

```markdown
### AUTH_INVALID_TOKEN

**HTTP Status:** 401  
**Message:** "Invalid or expired authentication token"  
**Cause:** Token is malformed, expired, or revoked  
**Resolution:** Re-authenticate and obtain a new token
```

---

## Security Documentation

### When to Document Security

- Authentication changes
- Authorization rule changes
- Sensitive data handling changes
- Security vulnerability fixes
- New security features

### Security Change Format

```markdown
### Security: [Brief Description]

**Severity:** Critical / High / Medium / Low  
**CVE:** CVE-XXXX-XXXXX (if applicable)  
**Affected Versions:** < 1.5.0  
**Fixed In:** 1.5.0

**Description:**
Brief description of the security issue or change.

**Impact:**
What could happen if exploited / What this change affects.

**Mitigation:**
Steps taken to fix or steps users should take.
```

### Security Changelog Entry

Always use the `### Security` section in CHANGELOG:

```markdown
### Security
- Fix authentication bypass vulnerability (CVE-2024-XXXXX)
- Upgrade bcrypt to address timing attack
```

### Sensitive Configuration

**Never document in public repos:**
- Actual secrets, API keys, passwords
- Production database credentials
- Private keys or certificates

**Do document:**
- Environment variable names
- Configuration structure
- Secret rotation procedures

---

## TODO.md Management

### TODO Item Format

```markdown
## [Category]

- [ ] **Task title** - Brief description
  - Priority: High/Medium/Low
  - Status: Not started / In progress / Blocked / Done
  - Assigned: @username or "Unassigned"
  - Notes: Additional context
```

### Status Markers

| Marker | Meaning |
|--------|---------|
| `- [ ]` | Not started |
| `- [~]` | In progress |
| `- [!]` | Blocked |
| `- [x]` | Completed |

### Categories

- **Features** - New functionality
- **Bugs** - Known issues to fix
- **Improvements** - Enhancements
- **Technical Debt** - Refactoring, cleanup
- **Documentation** - Doc tasks

### When to Update TODO.md

- New task identified → Add item
- Starting work → Mark in progress
- Task completed → Mark done or remove
- Task blocked → Mark blocked with reason

### Example TODO Entry

```markdown
## Features

- [ ] **Add bulk model import** - Import models from CSV file
  - Priority: Medium
  - Status: Not started
  - Notes: Should support CSV and Excel formats

- [x] **Add safe refresh button** - Allow adding new models without data loss
  - Priority: High
  - Status: Done
  - Completed: 2024-12-24
```

### TODO.md Housekeeping

Periodic maintenance keeps the TODO.md file organized and useful.

#### When to Perform Housekeeping
- At the end of major work sessions
- Before releases
- When completed items accumulate (5+ completed tasks)
- At least monthly

#### Housekeeping Checklist

```markdown
□ Remove or archive completed tasks older than 30 days
□ Update session summary with current stats
□ Verify all dates use correct year (watch for copy-paste errors)
□ Consolidate duplicate or related tasks
□ Re-prioritize tasks based on current project needs
□ Update "Last Housekeeping" date at bottom
□ Verify test count and coverage stats are current
□ Check for blocked tasks and update their status
□ Move tasks between priority levels if scope changed
```

#### Archive Format for Completed Tasks

When archiving completed tasks, move them to a "Completed Archive" section or remove entirely if well-documented in CHANGELOG:

```markdown
## Completed Archive (2025-Q4)

| Task | Completed | Notes |
|------|-----------|-------|
| Add soft delete | 2025-12-20 | See CHANGELOG v2.30.0 |
| Optimize queries | 2025-12-22 | Eager loading added |
```

#### Session Summary Template

Keep the Session Summary section updated:

```markdown
## Session Summary

**Branch:** `feature/branch-name`  
**Current Version:** vX.Y.Z  
**Test Count:** N tests  
**Coverage:** X% on module

### Session Achievements
- ✅ Achievement 1
- ✅ Achievement 2

### Backlog Status
| Priority | Status |
|----------|--------|
| High | ✅ Complete / N remaining |
| Medium | ✅ Complete / N remaining |
| Low | N future enhancements |

---

*Last Updated: YYYY-MM-DD*  
*Last Housekeeping: YYYY-MM-DD*
```

---

## Testing Documentation

### Test File Naming

| Test Type | File Pattern | Example |
|-----------|--------------|---------|
| Unit tests | `test_<module>.py` | `test_crud.py` |
| Integration | `test_<feature>_integration.py` | `test_auth_integration.py` |
| E2E | `test_e2e_<flow>.py` | `test_e2e_payroll.py` |

### Test Documentation Format

```python
def test_add_new_models_to_empty_schedule():
    """Test adding models to a schedule with no existing payouts.
    
    Given:
        - A schedule run exists with 0 payouts
        - 3 active models exist in database
    
    When:
        - add_new_models_to_run() is called
    
    Then:
        - 3 payouts are created
        - Existing schedule metadata unchanged
        - Returns count of added models
    """
```

### When to Add Test Documentation

- Complex test logic
- Non-obvious test setup
- Edge case tests
- Integration/E2E tests
- Tests for bug fixes (include bug reference)

### Test Coverage Documentation

Document coverage expectations:

```markdown
## Test Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| crud.py | 80% | 75% |
| services.py | 85% | 82% |
| auth.py | 90% | 88% |
```

---

## Deprecation Process

### Deprecation Timeline

1. **Announce** - Mark as deprecated in code + CHANGELOG
2. **Warn** - Log warnings when deprecated feature used
3. **Document** - Update docs with migration path
4. **Remove** - Remove in next major version

### Code Deprecation Markers

```python
import warnings

def old_function():
    """Deprecated: Use new_function() instead."""
    warnings.warn(
        "old_function is deprecated, use new_function instead",
        DeprecationWarning,
        stacklevel=2
    )
    return new_function()
```

### CHANGELOG Deprecation Entry

```markdown
### Deprecated
- `old_function()` - Use `new_function()` instead. Will be removed in v2.0.0
- `/api/v1/legacy-endpoint` - Use `/api/v1/new-endpoint`. Removal in v2.0.0
```

### Deprecation Notice Template

```markdown
## Deprecation Notice: [Feature Name]

**Deprecated In:** v1.5.0  
**Will Be Removed In:** v2.0.0  
**Replacement:** [New feature/approach]

### Migration Steps

1. Step one
2. Step two
3. Step three

### Why?

Brief explanation of why this is being deprecated.
```

---

## Troubleshooting Documentation

### When to Add Troubleshooting Docs

- Common user-reported issues
- Complex setup problems
- Environment-specific issues
- Known limitations

### Troubleshooting Entry Format

```markdown
### Problem: [Brief Description]

**Symptoms:**
- What the user sees/experiences

**Cause:**
- Why this happens

**Solution:**
1. Step-by-step fix

**Prevention:**
- How to avoid in future
```

### Example Entry

```markdown
### Problem: Payout data disappears after viewing schedule

**Symptoms:**
- Updated payout status/notes are lost
- Data reverts to previous state

**Cause:**
- Auto-refresh was enabled on schedule view
- Viewing the page triggered payroll regeneration

**Solution:**
1. Update to v1.5.0 or later
2. Auto-refresh has been removed

**Prevention:**
- Keep PayrollDesk updated to latest version
```

### Troubleshooting Categories

- **Installation** - Setup and dependency issues
- **Configuration** - Environment and settings issues
- **Authentication** - Login and permission issues
- **Data** - Data integrity and display issues
- **Performance** - Slow queries, timeouts
- **Integration** - Third-party service issues

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCUMENTATION QUICK REF                      │
├─────────────────────────────────────────────────────────────────┤
│ New Feature?                                                    │
│   → CHANGELOG (Added), Version bump (minor), README if visible  │
├─────────────────────────────────────────────────────────────────┤
│ Bug Fix?                                                        │
│   → CHANGELOG (Fixed), Version bump (patch)                     │
├─────────────────────────────────────────────────────────────────┤
│ Breaking Change?                                                │
│   → CHANGELOG, Version bump (major), MIGRATION_GUIDE, README    │
├─────────────────────────────────────────────────────────────────┤
│ Database Change?                                                │
│   → CHANGELOG, MIGRATION_GUIDE, Version bump (minor)            │
├─────────────────────────────────────────────────────────────────┤
│ Security Fix?                                                   │
│   → CHANGELOG (Security), Version bump (patch), CVE if needed   │
├─────────────────────────────────────────────────────────────────┤
│ API Change?                                                     │
│   → CHANGELOG, API docs, Version bump (minor/major)             │
├─────────────────────────────────────────────────────────────────┤
│ Deprecation?                                                    │
│   → CHANGELOG (Deprecated), Code warnings, Migration docs       │
├─────────────────────────────────────────────────────────────────┤
│ Version Location: app/__init__.py                               │
│ Commit Format: type(scope): description                         │
│ Branch Format: feature|fix|hotfix/<name>                        │
└─────────────────────────────────────────────────────────────────┘
```

---

*Last updated: 2024-12-24*
