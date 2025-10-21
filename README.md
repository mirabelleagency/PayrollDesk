# Payroll Desk

Automates recurring payroll schedules for the agency, supports manual roster imports via CLI, and now provides a web UI for managing models and schedule runs with persistent storage.

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

Launch the FastAPI server to manage models, run schedules, and download exports via the browser:

```powershell
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000` and use the navigation links to:

- Add, edit, or delete model records
- Trigger payroll runs for the target month
- Inspect payout schedules and validation findings
- Download Excel/CSV exports generated for each run

The application stores data in `data/payroll.db` (SQLite). Override the location by setting the `PAYROLL_DATABASE_URL` environment variable.

## Running Tests

```powershell
python -m pytest
```

Sample data is available in `models_sample.csv` for quick experimentation.

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
