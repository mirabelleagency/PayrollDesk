"""Database configuration for the payroll web application.

This module handles:
- Database engine creation with dual SQLite/PostgreSQL support
- Session management for FastAPI dependency injection
- Initial database setup (tables and default admin user)
- Query timing/logging (enable with LOG_QUERIES=true)

Schema migrations are handled by Alembic (see migrations/ folder).
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Default SQLite path for local development
DEFAULT_SQLITE_PATH = Path("data/payroll.db")
DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv("PAYROLL_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def _mask_db_url(url: str) -> str:
    """Redact credentials when logging database URLs.
    
    Transforms 'postgresql://user:secret@host/db' to 'postgresql://user:****@host/db'
    """
    try:
        parts = urlsplit(url)
        if "@" not in parts.netloc:
            return url
        creds, _, host_part = parts.netloc.partition("@")
        if ":" not in creds:
            return url
        username = creds.split(":", 1)[0]
        masked_netloc = f"{username}:****@{host_part}"
        return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Enable foreign key enforcement for SQLite connections.
    
    SQLite does not enforce foreign keys by default. This listener ensures
    that every connection to an SQLite database has foreign keys enabled,
    matching PostgreSQL's default behavior.
    """
    if "sqlite" in str(engine.url):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()


def _enable_query_logging(engine: Engine) -> None:
    """Enable query timing and logging for debugging and performance monitoring.
    
    Logs slow queries (>100ms) at WARNING level, all queries at DEBUG level.
    Only enabled when LOG_QUERIES environment variable is set.
    """
    if not os.getenv("LOG_QUERIES", "").lower() in ("1", "true", "yes"):
        return
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("query_start_time", [])
        if start_times:
            elapsed_ms = (time.perf_counter() - start_times.pop()) * 1000
            # Truncate long statements for logging
            stmt_preview = statement[:200] + "..." if len(statement) > 200 else statement
            stmt_preview = stmt_preview.replace("\n", " ")
            
            if elapsed_ms > 100:  # Slow query threshold
                logger.warning("SLOW QUERY (%.2fms): %s", elapsed_ms, stmt_preview)
            else:
                logger.debug("Query (%.2fms): %s", elapsed_ms, stmt_preview)


def _create_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine with appropriate settings.
    
    Configures:
    - SQLite: check_same_thread=False for FastAPI compatibility
    - PostgreSQL: connection pooling for production workloads
    """
    is_sqlite = url.startswith("sqlite")
    
    if is_sqlite:
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    else:
        # PostgreSQL with connection pooling
        return create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Verify connections before use
            future=True,
        )


def _initialize_engine() -> Engine:
    """Initialize the database engine with retry and fallback support.
    
    Retries connection with exponential backoff before falling back.
    In development, falls back to SQLite if PostgreSQL is unavailable.
    In production, fails loudly if the database is unreachable.
    
    Environment Variables:
        DB_CONNECT_RETRIES: Number of retry attempts (default: 3)
        DB_RETRY_DELAY: Initial delay between retries in seconds (default: 1.0)
    """
    global DATABASE_URL
    
    masked_url = 'sqlite:///*' if DATABASE_URL.startswith('sqlite') else _mask_db_url(DATABASE_URL)
    env = os.getenv("ENVIRONMENT", "production").lower()
    logger.info("ENVIRONMENT=%s | DATABASE_URL=%s", env, masked_url)
    
    # Retry configuration
    max_retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
    base_delay = float(os.getenv("DB_RETRY_DELAY", "1.0"))
    
    last_error: Exception | None = None
    
    for attempt in range(1, max_retries + 1):
        try:
            engine = _create_engine(DATABASE_URL)
            _enable_sqlite_foreign_keys(engine)
            _enable_query_logging(engine)
            # Smoke-test connection
            with engine.connect():
                pass
            if attempt > 1:
                logger.info("Database connection succeeded on attempt %d", attempt)
            return engine
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(
                    "Database connection attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt, max_retries, e, delay
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "Database connection attempt %d/%d failed: %s",
                    attempt, max_retries, e
                )
    
    # All retries exhausted - try fallback
    is_dev = env in ("development", "dev", "local")
    allow_fallback = os.getenv("LOCAL_DEV_SQLITE_FALLBACK", str(is_dev)).lower() in ("1", "true", "yes")
    
    if is_dev and allow_fallback:
        DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"
        logger.info("Falling back to SQLite (dev-only): %s", DATABASE_URL)
        engine = _create_engine(DATABASE_URL)
        _enable_sqlite_foreign_keys(engine)
        return engine
    else:
        logger.error("Database connection failed after %d attempts; aborting startup", max_retries)
        raise last_error or RuntimeError("Database connection failed")


# Initialize engine and session factory
engine = _initialize_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_session)):
            return db.query(Item).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Initialize database tables and create default admin user.
    
    This is called on application startup. For schema migrations,
    use Alembic: `alembic upgrade head`
    """
    from app import models  # noqa: F401 - registers models with Base.metadata
    from app.auth import User

    # Create tables (no-op if they exist)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.debug("Table already exists (normal on restart): %s", e)
        else:
            logger.warning("Table creation warning: %s", e)

    # Create default admin user if needed
    session = SessionLocal()
    try:
        admin_exists = session.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            admin_user = User.create_user("admin", "admin", role="admin")
            session.add(admin_user)
            session.commit()
            logger.info("Created default admin user (username: admin)")
    except Exception as e:
        logger.error("Error creating admin user: %s", e)
        session.rollback()
    finally:
        session.close()

