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
