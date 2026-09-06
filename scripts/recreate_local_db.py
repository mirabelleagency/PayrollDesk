"""Recreate local SQLite dev database with v4 schema and admin/admin."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "payroll_v4.db"

os.environ["PAYROLL_DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["ENVIRONMENT"] = "development"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "admin"
os.environ["API_RATE_SECRET"] = "dev-rate-secret-for-local-testing-32c"
os.environ["API_CURSOR_SECRET"] = "dev-cursor-secret-for-local-test-32c"

if DB.exists():
    DB.unlink()
for suffix in ("-shm", "-wal"):
    extra = DB.with_name(DB.name + suffix)
    if extra.exists():
        extra.unlink()

sys.path.insert(0, str(ROOT))

from app.database import init_db

init_db()
print("init_db complete")

result = subprocess.run(
    [sys.executable, "-m", "alembic", "stamp", "head"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)

print("alembic stamped to head")
print("Login: admin / admin")
print("URL: http://127.0.0.1:8000/login")
