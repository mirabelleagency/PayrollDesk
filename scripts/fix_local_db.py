"""Bring local payroll.db schema up to date for v4 dev."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "payroll.db"


def inspect_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
    row = cur.fetchone()
    print("alembic_version table:", row)
    if row:
        cur.execute("SELECT version_num FROM alembic_version")
        print("revision:", cur.fetchone()[0])
    cur.execute("PRAGMA table_info(schedule_runs)")
    print("schedule_runs cols:", [r[1] for r in cur.fetchall()])
    cur.execute("PRAGMA table_info(api_keys)")
    print("api_keys cols:", [r[1] for r in cur.fetchall()] or "missing")
    conn.close()


def reset_admin() -> None:
    os.environ.setdefault("PAYROLL_DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
    from app.auth import User
    from app.database import SessionLocal
    from app.security import unlock_account

    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.username == "admin").first()
        if admin is None:
            admin = User.create_user("admin", "admin", role="admin")
            session.add(admin)
        else:
            admin.password_hash = User.hash_password("admin")
            unlock_account(session, "admin")
        session.commit()
        print("admin unlocked with password: admin")
    finally:
        session.close()


if __name__ == "__main__":
    inspect_db()
    reset_admin()
