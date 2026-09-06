# Start PayrollDesk locally with a fresh v4 SQLite database.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$env:PAYROLL_DATABASE_URL = "sqlite:///./data/payroll_v4.db"
$env:ENVIRONMENT = "development"
$env:ADMIN_DEFAULT_PASSWORD = "admin"
$env:API_RATE_SECRET = "dev-rate-secret-for-local-testing-32c"
$env:API_CURSOR_SECRET = "dev-cursor-secret-for-local-test-32c"

if (-not (Test-Path "data/payroll_v4.db")) {
    python scripts/recreate_local_db.py
}

Write-Host "Starting PayrollDesk on http://127.0.0.1:8002"
Write-Host "Login: admin / admin"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
