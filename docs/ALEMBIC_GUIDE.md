# Database Migrations with Alembic

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

## Quick Start

### Check Current Version
```bash
alembic current
```

### Apply All Pending Migrations
```bash
alembic upgrade head
```

### Rollback One Version
```bash
alembic downgrade -1
```

### View Migration History
```bash
alembic history
```

## Creating New Migrations

### Option 1: Auto-generate (Recommended)
When you modify SQLAlchemy models in `app/models.py`:

```bash
# Generate migration by comparing models to database
alembic revision --autogenerate -m "add notes column to models"
```

**Review the generated file!** Auto-generate catches most changes but may miss some edge cases.

### Option 2: Manual Migration
For complex changes or data migrations:

```bash
# Create empty migration
alembic revision -m "migrate status values"
```

Then edit the generated file in `migrations/versions/`.

## Example Migration

```python
"""add notes column to models

Revision ID: abc123
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = '0001'

def upgrade():
    op.add_column('models', sa.Column('notes', sa.String(500), nullable=True))

def downgrade():
    op.drop_column('models', 'notes')
```

## Migration Workflow

1. **Develop locally**: Make model changes, create migration
2. **Test locally**: Run `alembic upgrade head` on dev database
3. **Commit**: Include both model changes AND migration file
4. **Deploy**: Production runs `alembic upgrade head` on startup

## Common Operations

| Operation | Command |
|-----------|---------|
| Apply all migrations | `alembic upgrade head` |
| Rollback one step | `alembic downgrade -1` |
| Go to specific version | `alembic upgrade abc123` |
| View current version | `alembic current` |
| View pending migrations | `alembic history --indicate-current` |
| Generate from model changes | `alembic revision --autogenerate -m "description"` |
| Create empty migration | `alembic revision -m "description"` |

## Production Deployment

### Option 1: In entrypoint.sh (Recommended)
```bash
#!/bin/bash
alembic upgrade head
exec gunicorn app.main:app ...
```

### Option 2: Render.com Pre-deploy Command
In `render.yaml`:
```yaml
services:
  - type: web
    buildCommand: pip install -r requirements.txt && alembic upgrade head
```

## Stamping Existing Databases

For databases that existed before Alembic was added:

```bash
# Stamp without running any migrations
alembic stamp 0001
```

This tells Alembic "this database is at version 0001" without making any schema changes.

## Troubleshooting

### "Target database is not up to date"
```bash
alembic upgrade head
```

### "Can't locate revision"
Check that migration files exist in `migrations/versions/`.

### Autogenerate missing changes
Some changes aren't detected by autogenerate:
- Table name changes
- Column name changes
- Some constraint changes

Create manual migrations for these.

## File Structure

```
migrations/
├── env.py           # Alembic environment configuration
├── script.py.mako   # Template for new migrations
├── README           # Alembic README
└── versions/        # Migration scripts
    └── 0001_initial_baseline.py
```

## Database Backend

Migrations target **PostgreSQL** (the production and development database). The `env.py` is configured to use the `PAYROLL_DATABASE_URL` environment variable. Tests use a temporary SQLite database but do not run migrations.

## Version History

| Version | Description | Date |
|---------|-------------|------|
| 0001 | Initial baseline (stamp existing schema) | 2024-12-24 |
