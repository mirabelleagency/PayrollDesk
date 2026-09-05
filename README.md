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

The application stores data in `data/payroll.db` (SQLite). Override the location by setting the `PAYROLL_DATABASE_URL` environment variable.

### Switching between SQLite (dev) and Postgres (prod)

- Local development: set `ENVIRONMENT=development` (or `dev`) and run the server. If a Postgres URL is unreachable, the app now falls back to the bundled SQLite database automatically. To **force Postgres failures locally**, set `LOCAL_DEV_SQLITE_FALLBACK=0`.
- Production/staging: set `ENVIRONMENT=production` (or leave unset) and point `PAYROLL_DATABASE_URL` to your managed Postgres instance. In these environments the SQLite fallback stays disabled unless you explicitly set `LOCAL_DEV_SQLITE_FALLBACK=1`.

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
	- `LOCAL_DEV_SQLITE_FALLBACK` = `false` (optional — defaults to disabled in production)

3) Redeploy/restart
- Save the variables and trigger a deploy/restart so the app reconnects using Postgres.

4) Verify the backend in production
- Log in as an admin and open `/admin/diagnostics/db`.
- You should see a JSON response with `dialect: "postgresql"` and `is_postgres: true`.

Notes
- Do not commit secrets in `render.yaml`; set them in the Render UI.
- The included `render.yaml` targets branch `main` for deployments.

Data migration from SQLite (optional)
- If you already have data in `data/payroll.db` and need it in Postgres, create a one-off migration before switching.
- We can provide a script that reads from `sqlite:///data/payroll.db` and writes to your Postgres URL, copying tables in a safe order. Ask for the "SQLite → Postgres migration script" to add it to the repo with a short runbook.

## External Pull API

Read-only JSON endpoints under `/api/v1` let another system synchronize payroll data. Authenticate with an API key in the `X-API-Key` header.

### Create an API key

1. Log in as an admin.
2. Open **Admin → API Keys**.
3. Create a key and copy the secret immediately — it is shown only once.

### Example request

```powershell
curl -s -H "X-API-Key: pd_your_key_here" "http://127.0.0.1:8000/api/v1/models?limit=100"
```

List endpoints return:

```json
{
  "data": [ ... ],
  "pagination": {
    "limit": 100,
    "next_cursor": 123,
    "has_more": true
  }
}
```

Traverse pages with `after_id=<next_cursor>` until `has_more` is false. Detail endpoints return `{"data": {...}}`.

### Synchronization model (v1)

This API is designed for **periodic full scans**, not live incremental mirroring:

1. Pull each collection you need, page by page, with stable `id ASC` ordering.
2. Stage results locally before updating your downstream system.
3. Reconcile deletions only after a **complete, unfiltered** pass of that collection finishes successfully.
4. If a payroll run is regenerated while you are pulling, restart the affected collections — there is no snapshot token or revision check in v1.

Filtered queries (date ranges, status, etc.) are for narrowing exports, not authoritative deletion detection.

### Integration limitations

Be aware of these behaviors when building an exact external mirror:

| Topic | Behavior |
|-------|----------|
| Concurrent writes | Payroll regeneration can delete and recreate payouts/validations mid-sync. Rows may disappear, reappear with new IDs, or shift between pages. |
| Payout identity | Payout primary keys are not stable across schedule regeneration for the same logical pay period. |
| Payout amounts | `amount` on payouts is **net** after planned advance deductions. Use `advance-allocations` (planned) and `advance-repayments` (realized) to reconstruct deductions. |
| Wallets | `crypto_wallet` on payouts comes from the current model record, not a historical snapshot. |
| Datetimes | Stored and returned as timezone-naive ISO strings (server local time). |
| Cross-resource consistency | No guarantee that two collections reflect the same point in time; pull during quiet periods or retry on mismatch. |

Future versions may add revision tokens, stable payout identity, and explicit gross/net amount fields if strict mirroring is required.

### API v2 (stable mirroring)

`/api/v2` is read-only (`GET`/`HEAD` only) and adds snapshot revision checks, stable payout identity `(schedule_run_id, code, pay_date)`, persisted gross/net amounts, UTC datetimes with trailing `Z`, scoped API keys, and HMAC-signed pagination cursors.

**Synchronization algorithm**

1. `GET /api/v2/snapshot` — record `revision` and authorized `collections`.
2. For each authorized collection, pull all pages with the same filters and `limit`. Every first page must include `snapshot_revision` from step 1; later pages use `next_cursor`.
3. On `409 snapshot_changed`, discard the entire staged generation and restart from step 1.
4. On network/`5xx` errors, retry the same request/cursor. On `429`, wait for `Retry-After`.
5. On `401`/`403`, stop and fix credentials/scopes.
6. After all authorized collections complete, call `/api/v2/snapshot` again. Publish staged data only if the revision matches step 1.

**Production environment variables (v2)**

| Variable | Required outside dev/test | Purpose |
|----------|---------------------------|---------|
| `API_CURSOR_SECRET` | Yes (min 32 chars) | Signs v2 pagination cursors |
| `API_RATE_SECRET` | Yes (min 32 chars) | HMAC bucket IDs for rate limiting |
| `API_V2_ENABLED` | No (default `true`) | Set `false` during expand/contract rollout |

Existing API keys are migrated to `v1:*` only; grant explicit `v2:*` or `v2:<resource>` scopes for v2 access.

### Formats

- Dates: ISO `YYYY-MM-DD`
- Datetimes: ISO strings (timezone-naive, as stored)
- Money and rates: decimal strings (e.g. `"1250.00"`)

### Available collections

- `/api/v1/models`, `/api/v1/payouts`, `/api/v1/schedule-runs`
- `/api/v1/validation-issues`, `/api/v1/adhoc-payments`, `/api/v1/adjustments`
- `/api/v1/advances`, `/api/v1/advance-repayments`, `/api/v1/advance-allocations`

OpenAPI docs: `http://127.0.0.1:8000/docs`

### Production environment variables

| Variable | Required in production/staging | Purpose |
|----------|-------------------------------|---------|
| `SESSION_SECRET` | Yes (min 32 chars) | Signs browser admin sessions |
| `ADMIN_INITIAL_PASSWORD` | Yes on first deploy (min 12 chars) | Creates the initial admin user when none exists |
| `PAYROLL_DATABASE_URL` | Yes | Database connection |
| `ENVIRONMENT` | Recommended | Use `production` on Render; `development` or `test` locally only |
| `API_CURSOR_SECRET` | Yes for v2 | Signs v2 pagination cursors (min 32 chars) |
| `API_RATE_SECRET` | Yes for API | Rate limit bucket HMAC (min 32 chars) |
| `API_V2_ENABLED` | No | Set `false` during rollout; default enables v2 |

Use HTTPS in production and staging. API keys grant read access to all payroll PII (names, wallets, amounts). Change the default `admin/admin` password before deploying — startup fails if `admin/admin` remains outside development/test.

## Running Tests

```powershell
python -m pytest
```

Sample data is available in `models_sample.csv` for quick experimentation.

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
