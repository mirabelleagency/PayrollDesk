"""Database configuration for the payroll web application."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DEFAULT_SQLITE_PATH = Path("data/payroll.db")
DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("PAYROLL_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def _mask_db_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        netloc = parts.netloc
        if "@" not in netloc:
            return url
        creds, _, host_part = netloc.partition("@")
        if ":" not in creds:
            return url
        username = creds.split(":", 1)[0]
        masked_netloc = f"{username}:****@{host_part}"
        return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def _configure_sqlite_connection(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def _create_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    eng = create_engine(url, connect_args=connect_args, future=True)
    if eng.dialect.name == "sqlite":
        event.listen(eng, "connect", _configure_sqlite_connection)
    return eng


masked_url = "sqlite:///*" if DATABASE_URL.startswith("sqlite") else _mask_db_url(DATABASE_URL)
print(f"[database] ENVIRONMENT={os.getenv('ENVIRONMENT', 'unset')} | PAYROLL_DATABASE_URL={masked_url}")

try:
    engine = _create_engine(DATABASE_URL)
    with engine.connect() as _conn:
        pass
except Exception as e:  # pragma: no cover
    env = os.getenv("ENVIRONMENT", "production").lower()
    default_fallback_flag = "true" if env in ("development", "dev", "local") else "false"
    allow_dev_fallback = os.getenv("LOCAL_DEV_SQLITE_FALLBACK", default_fallback_flag).lower() in ("1", "true", "yes")
    print(f"[database] Could not connect to database at {DATABASE_URL!r}: {e}")
    if env in ("development", "dev", "local") and allow_dev_fallback:
        fallback = f"sqlite:///{DEFAULT_SQLITE_PATH}"
        print(f"[database] Falling back to SQLite (dev-only) at {fallback}")
        DATABASE_URL = fallback
        engine = _create_engine(DATABASE_URL)
    else:
        print("[database] Fallback disabled; aborting startup")
        raise

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()
_sync_events_registered = False


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_api_read_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    session.info["read_only_api"] = True
    try:
        if session.bind and session.bind.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
    finally:
        session.close()


def init_db() -> None:
    global _sync_events_registered
    from app import models  # noqa: F401
    from app.auth import User
    from app.migrations import SCHEMA_VERSION, upgrade, verify_schema
    from app.sync import register_sync_events

    if not _sync_events_registered:
        register_sync_events()
        _sync_events_registered = True

    try:
        verify_schema(engine)
    except RuntimeError:
        env = os.getenv("ENVIRONMENT", "production").lower()
        if env in ("development", "dev", "local", "test"):
            upgrade(engine)
            verify_schema(engine)
        else:
            raise

    session = SessionLocal()
    try:
        from app.session_config import is_development_environment

        admin = session.query(User).filter(User.username == "admin").first()
        if admin is None:
            if is_development_environment():
                admin_password = "admin"
                print("[init_db] Created default admin user (username: admin, password: admin, role: admin)")
            else:
                initial_password = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip()
                if not initial_password:
                    raise RuntimeError(
                        "No admin user exists and ADMIN_INITIAL_PASSWORD is not set. "
                        f"Set ADMIN_INITIAL_PASSWORD before starting with ENVIRONMENT={os.getenv('ENVIRONMENT', 'production')!r}."
                    )
                if len(initial_password) < 12:
                    raise RuntimeError("ADMIN_INITIAL_PASSWORD must be at least 12 characters.")
                admin_password = initial_password
                print("[init_db] Created admin user from ADMIN_INITIAL_PASSWORD (username: admin)")
            session.add(User.create_user("admin", admin_password, role="admin"))
            session.commit()
        else:
            print("[init_db] Admin user already exists, skipping creation")
            if not is_development_environment() and admin.verify_password("admin"):
                raise RuntimeError(
                    "Default admin/admin credentials detected. Change the admin password before "
                    f"running with ENVIRONMENT={os.getenv('ENVIRONMENT', 'production')!r}."
                )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"[init_db] Schema verified at version {SCHEMA_VERSION}")
