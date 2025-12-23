# Contributing to PayrollDesk

Thank you for your interest in contributing to PayrollDesk! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please:

- Be respectful of differing viewpoints
- Accept constructive criticism gracefully
- Focus on what is best for the project
- Show empathy towards other contributors

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- VS Code (recommended)

### Finding Issues to Work On

1. Check the [Issues](../../issues) page
2. Look for labels like `good first issue` or `help wanted`
3. Comment on an issue before starting work

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/PayrollDesk.git
cd PayrollDesk
```

### 2. Create Virtual Environment

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS/Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your local settings
# For development, defaults should work:
# ENVIRONMENT=development
# LOCAL_DEV_SQLITE_FALLBACK=true
```

### 5. Initialize Database

The database initializes automatically on first run.

### 6. Run the Application

```bash
# Option 1: Direct uvicorn
uvicorn app.main:app --reload

# Option 2: VS Code task (recommended)
# Use "Run Uvicorn Server (SQLite Dev)" task
```

Visit `http://127.0.0.1:8000` to verify setup.

### 7. Run Tests

```bash
python -m pytest
```

## Making Changes

### Branching Strategy

We follow a Git Flow-inspired model:

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code |
| `develop` | Integration branch |
| `staging` | Pre-release testing |
| `feature/*` | New features |
| `hotfix/*` | Urgent fixes |
| `release/*` | Release preparation |

### Creating a Feature Branch

```bash
# Start from develop
git checkout develop
git pull origin develop

# Create your branch
git checkout -b feature/your-feature-name
```

### Commit Messages

Use conventional commit format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `style:` Code style (formatting, semicolons)
- `refactor:` Code refactoring
- `test:` Adding/updating tests
- `chore:` Maintenance tasks

**Examples:**
```
feat(models): add bulk import functionality
fix(schedules): correct date calculation for biweekly payments
docs(readme): update installation instructions
test(auth): add login redirect coverage
```

### Keeping Your Branch Updated

```bash
git checkout develop
git pull origin develop
git checkout feature/your-feature-name
git rebase develop
```

## Pull Request Process

### Before Submitting

1. **Update your branch** from `develop`
2. **Run tests** - All tests must pass
3. **Check formatting** - Code should be clean
4. **Update documentation** if needed
5. **Update CHANGELOG.md** with your changes

### Submitting

1. Push your branch:
   ```bash
   git push -u origin feature/your-feature-name
   ```

2. Open a Pull Request against `develop`

3. Fill out the PR template:
   - Description of changes
   - Related issues
   - Type of change
   - Checklist completion

### PR Review

- At least one approval required
- Address review feedback promptly
- Keep PRs focused and reasonably sized
- Large changes should be split into smaller PRs

### After Merge

- Delete your feature branch
- Pull the updated `develop` branch

## Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with these specifics:

```python
# Line length: 100 characters max
# Indentation: 4 spaces
# Quotes: Double quotes for strings

# Good
def calculate_payout(model: Model, month: int) -> Decimal:
    """Calculate monthly payout for a model."""
    if model.payment_frequency == "monthly":
        return model.amount_monthly
    return model.amount_monthly / 2


# Bad
def calculate_payout(model,month):
    if model.payment_frequency=='monthly': return model.amount_monthly
    return model.amount_monthly/2
```

### Type Hints

Use type hints for function signatures:

```python
from decimal import Decimal
from typing import Optional

def get_model_by_code(db: Session, code: str) -> Optional[Model]:
    """Retrieve a model by its unique code."""
    return db.query(Model).filter(Model.code == code).first()
```

### Docstrings

Use docstrings for modules, classes, and functions:

```python
def create_schedule_run(
    db: Session,
    target_year: int,
    target_month: int,
    run_number: int = 1
) -> ScheduleRun:
    """
    Create a new payroll schedule run.

    Args:
        db: Database session
        target_year: Year for the schedule
        target_month: Month for the schedule (1-12)
        run_number: Run number within the month

    Returns:
        The created ScheduleRun instance

    Raises:
        ValueError: If month is not 1-12
    """
    ...
```

### Imports

Organize imports in this order:

```python
# Standard library
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Local application
from app.models import Model, Payout
from app.schemas import ModelCreate
from app.database import get_db
```

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_auth_redirect.py

# Run with coverage
python -m pytest --cov=app
```

### Writing Tests

Place tests in the `tests/` directory:

```python
# tests/test_example.py
import pytest
from app.crud import create_model

def test_create_model_success(db_session):
    """Test that models are created correctly."""
    model = create_model(
        db_session,
        code="TEST001",
        real_name="Test User",
        working_name="Test"
    )
    
    assert model.id is not None
    assert model.code == "TEST001"


def test_create_model_duplicate_code(db_session):
    """Test that duplicate codes raise an error."""
    create_model(db_session, code="DUP001", ...)
    
    with pytest.raises(IntegrityError):
        create_model(db_session, code="DUP001", ...)
```

### Test Fixtures

Use fixtures from `conftest.py`:

```python
# conftest.py provides:
# - db_session: Fresh database session
# - test_client: FastAPI test client
# - sample_model: Pre-created test model
```

## Documentation

### When to Update Docs

- README.md: Installation, usage, or configuration changes
- CHANGELOG.md: All user-facing changes
- Code comments: Complex logic or non-obvious decisions
- Docstrings: New or modified functions

### CHANGELOG Format

Add entries under `## [Unreleased]`:

```markdown
## [Unreleased]

### Added
- feat(models): bulk import from Excel files

### Fixed
- fix(schedules): date calculation for February
```

## Questions?

- Check existing [issues](../../issues)
- Open a new issue for questions
- Tag maintainers if urgent

---

Thank you for contributing to PayrollDesk! 🎉
