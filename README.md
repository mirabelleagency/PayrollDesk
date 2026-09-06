# Payroll Desk

Automates recurring payroll schedules for the agency, supports manual roster imports via CLI, and now provides a web UI for managing models and payroll cycles with persistent storage.

## Requirements

Install dependencies with:

```powershell
pip install -r requirements.txt
```

## CLI Usage

Generate an export from CSV or Excel using the existing command-line interface:

```powershell
python payroll.py --month 2025-11 --input models_sample.csv --out dist --preview
```

The CLI writes Excel and CSV bundles to the chosen output directory and prints a summary line to the console.

## Web Application

Launch the FastAPI server to manage models, orchestrate payroll cycles, and download exports via the browser:

```powershell
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000` and use the navigation links to:

- Add, edit, or delete model records
- Trigger payroll cycles for the target month
- Inspect payout schedules and validation findings
- Download Excel/CSV exports generated for each cycle

The application uses PostgreSQL for all environments. Set the `PAYROLL_DATABASE_URL` environment variable to your connection string.

For local development, use the included Docker Compose file:

```powershell
docker compose -f docker-compose.dev.yml up -d
```

This starts PostgreSQL on `localhost:5432` with credentials `payroll/payroll`.

### Database Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYROLL_DATABASE_URL` | `postgresql://payroll:payroll@localhost:5432/payroll_dev` | Database connection URL |
| `ENVIRONMENT` | `production` | Environment mode (development/production) |
| `DB_CONNECT_RETRIES` | `3` | Connection retry attempts |
| `DB_RETRY_DELAY` | `1.0` | Initial retry delay in seconds |
| `DB_POOL_SIZE` | `5` | PostgreSQL min connections |
| `DB_MAX_OVERFLOW` | `10` | PostgreSQL max additional connections |
| `DB_POOL_RECYCLE` | `3600` | Seconds before recycling connections |
| `LOG_QUERIES` | `false` | Enable query timing logs (slow >100ms)

## Production database on Render (Postgres)

Use PostgreSQL in production to avoid data loss across deploys and dyno restarts.

1) Provision Postgres on Render
- Create a managed Postgres named `payrolldeskdb` (or your choice).
- On the database page, copy the Internal Connection String (preferred when the app also runs on Render). It looks like:
	`postgresql://USER:PASSWORD@HOST:5432/payrolldeskdb?sslmode=require`

2) Configure the web service environment variables
- In your Render web service ("payroll-desk"), add/update:
	- `PAYROLL_DATABASE_URL` = the Postgres connection string above
	- `ENVIRONMENT` = `production`

3) Redeploy/restart
- Save the variables and trigger a deploy/restart so the app reconnects using Postgres.

4) Verify the backend in production
- Log in as an admin and open `/admin/diagnostics/db`.
- You should see a JSON response with `dialect: "postgresql"` and `is_postgres: true`.

Notes
- Do not commit secrets in `render.yaml`; set them in the Render UI.
- The included `render.yaml` targets branch `main` for deployments.

Data migration
- For migrating data between PostgreSQL instances, use Alembic migrations and standard pg_dump/pg_restore tools.

## Running Tests

```powershell
python -m pytest
```

Sample data is available in `models_sample.csv` for quick experimentation.

## External read-only API (v1 / v2)

Server-to-server integration uses scoped API keys — not browser session cookies.

1. Set secrets (32+ characters each; required outside `development` / `test`):

   | Variable | Purpose |
   |----------|---------|
   | `API_RATE_SECRET` | HMAC salt for per-key and per-IP rate windows |
   | `API_CURSOR_SECRET` | HMAC salt for signed pagination cursors |

2. Log in as admin → **Admin → API Keys**, create a key (e.g. scope `v2:*`). Copy the plaintext secret once; only a prefix is stored.

3. Call the API with the header `X-API-Key: pd_…`:

   ```powershell
   curl -H "X-API-Key: pd_your_key" http://127.0.0.1:8000/api/v2/snapshot
   curl -H "X-API-Key: pd_your_key" "http://127.0.0.1:8000/api/v2/models?snapshot_revision=0"
   ```

   v2 collections require a current `snapshot_revision` from `/api/v2/snapshot`. If payroll data changes mid-sync, stale revisions return **409** — refresh the snapshot and retry.

Notes:

- CORS is closed; use curl or a backend client, not browser JS from another origin.
- `v2:*` exposes legal names, notes, and crypto wallet addresses — grant narrowly in production.
- Responses use `Cache-Control: no-store`.

## Versioning & Release Notes

- Run `python scripts/auto_bump_and_changelog.py` before pushing to `staging`, `develop`, or `main`. The helper bumps `app/__version__`, appends the latest commits to `CHANGELOG.md`, and tags the release when run in CI.
- The UI surfaces the active build number in the lower-right corner and exposes the full changelog at `/changelog` (also linked from the sidebar).
- Keep commit messages descriptive—those lines populate the release notes grouped under each version section.

## Branching Workflow

The repository follows a lightweight Git Flow inspired model:

- `main` — production-ready code. Deploy from this branch only.
- `develop` — integrates feature branches ahead of staging.
- `staging` — smoke testing and release candidate verification.
- `release/*` — version-specific polish before merging to `main` and back to `develop`.
- `hotfix/*` — urgent fixes cut from `main`, merged to both `main` and `develop`.

Typical cycle:

1. Create feature work off `develop`:
	```powershell
	git checkout develop
	git pull
	git checkout -b feature/<name>
	```
2. Merge feature into `develop` via pull request. Resolve conflicts and delete the feature branch once merged.
3. When ready to test, fast-forward `staging` from `develop`:
	```powershell
	git checkout staging
	git pull
	git merge --ff-only develop
	git push
	```
4. Cut a release branch when preparing a tagged deployment:
	```powershell
	git checkout develop
	git pull
	git checkout -b release/<version>
	git push -u origin release/<version>
	```
	Finalize changes, then merge the release branch to both `main` and `develop`, tagging the release on `main`.
5. For critical production fixes, branch from `main`:
	```powershell
	git checkout main
	git pull
	git checkout -b hotfix/<issue>
	```
	After validation, merge the hotfix into `main`, tag if needed, and merge back into `develop` to keep histories aligned.

## Documentation

Project documentation lives in `docs/`. See
[DOCUMENT-INDEX.md](docs/DOCUMENT-INDEX.md) for the
full index including archived docs.

| Document | Description |
|----------|-------------|
| [TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md) | Architecture, schema, API, security |
| [DESIGN_AUDIT.md](docs/DESIGN_AUDIT.md) | Design system, colors, typography, icons |
| [SCHEDULE_REVAMP.md](docs/SCHEDULE_REVAMP.md) | Schedule system 10-phase redesign |
| [ALEMBIC_GUIDE.md](docs/ALEMBIC_GUIDE.md) | Database migration guide (Alembic) |
| [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) | Data migration and CSV import |
| [DUPLICATE_HANDLING.md](docs/DUPLICATE_HANDLING.md) | Duplicate detection across imports |
| [ASSESSMENT_GUIDE.md](docs/ASSESSMENT_GUIDE.md) | Assessment and evaluation framework |
| [DOCUMENTATION_GUIDE.md](docs/DOCUMENTATION_GUIDE.md) | Documentation standards |

See also: [CHANGELOG.md](CHANGELOG.md) for release notes.
