# Quick Assessment Guide

A lean reference for ad-hoc code assessments on individual files, modules, or features.

---

## Assessment Command

Use this prompt format for assessments:

```
Assess [target] using the Quick Assessment Guide. Rate 1-10 and identify gaps.
```

**Examples:**
- "Assess `app/crud.py` using the Quick Assessment Guide"
- "Assess the authentication flow using the Quick Assessment Guide"
- "Assess our error handling using the Quick Assessment Guide"

---

## Rating Scale

| Rating | Level | Description |
|--------|-------|-------------|
| 9-10 | Excellent | Production-ready, well-documented, fully tested |
| 7-8 | Good | Solid implementation, minor improvements needed |
| 5-6 | Adequate | Works but has notable gaps |
| 3-4 | Needs Work | Significant issues, refactoring needed |
| 1-2 | Critical | Broken or major security/logic flaws |

---

## Category Checklists

### Code Quality
- [ ] Consistent naming conventions
- [ ] Type hints on functions/methods
- [ ] Docstrings on public functions
- [ ] No magic numbers (use constants)
- [ ] DRY - no duplicated logic
- [ ] Single responsibility per function
- [ ] Proper error handling

### Security
- [ ] Input validation
- [ ] SQL injection prevention (parameterized queries)
- [ ] Authentication checks on protected routes
- [ ] Authorization (role-based access)
- [ ] Sensitive data not logged
- [ ] Secure password handling

### Database/CRUD
- [ ] Uses transactions appropriately
- [ ] Handles None/null cases
- [ ] Proper cascade deletes
- [ ] Indexes on filtered columns
- [ ] N+1 query prevention (eager loading)
- [ ] Connection handling (session cleanup)

### API/Endpoints
- [ ] Consistent response format
- [ ] Proper HTTP status codes
- [ ] Validation on request inputs
- [ ] Error messages are informative
- [ ] Rate limiting on sensitive endpoints

### Testing
- [ ] Unit tests exist
- [ ] Edge cases covered
- [ ] Error paths tested
- [ ] Mocks used appropriately
- [ ] Tests are independent

### UI/Templates
- [ ] Consistent styling
- [ ] Error states displayed
- [ ] Loading states handled
- [ ] Mobile responsive
- [ ] Accessible (ARIA labels)

---

## Quick Assessment Template

```markdown
## Assessment: [Target Name]

**Rating: X/10**

### Strengths
- 
- 

### Gaps
| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 |       | High/Med/Low |     |

### Recommendations
1. 
2. 
```

---

## Severity Guide

| Severity | Description | Action |
|----------|-------------|--------|
| **Critical** | Security flaw, data loss risk | Fix immediately |
| **High** | Major bug, missing feature | Fix this sprint |
| **Medium** | Code smell, tech debt | Schedule fix |
| **Low** | Nice-to-have improvement | Backlog |

---

## Common Assessment Targets

### Files
- `app/crud.py` - Database operations
- `app/services.py` - Business logic
- `app/security.py` - Authentication/authorization
- `app/models.py` - Data models
- `app/routers/*.py` - API endpoints

### Concerns
- Error handling patterns
- Logging practices
- Configuration management
- Input validation
- Transaction safety
- Performance bottlenecks

### Features
- Login/authentication flow
- Payroll calculation
- Export generation
- Import processing
- Commission tracking

---

## Assessment Workflow

1. **Identify target** - File, module, or feature
2. **Gather context** - Read code, check tests
3. **Apply checklist** - Use relevant category
4. **Rate objectively** - Use scale above
5. **Document gaps** - List with severity
6. **Recommend fixes** - Prioritized actions
