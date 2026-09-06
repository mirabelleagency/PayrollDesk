"""Database configuration for the payroll web application.

This module handles:
- Database engine creation with PostgreSQL connection pooling
- Session management for FastAPI dependency injection
- Initial database setup (tables and default admin user)
- Query timing/logging (enable with LOG_QUERIES=true)

Schema migrations are handled by Alembic (see migrations/ folder)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Generator
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Database URL from environment (PostgreSQL required)
DATABASE_URL = os.getenv("PAYROLL_DATABASE_URL", "postgresql://payroll:payroll@localhost:5432/payroll_dev")


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
    """Create a SQLAlchemy engine with PostgreSQL connection pooling.
    
    Environment Variables:
        DB_POOL_SIZE: Min connections in pool (default: 5)
        DB_MAX_OVERFLOW: Max additional connections (default: 10)
        DB_POOL_RECYCLE: Seconds before recycling connections (default: 3600)
    """
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    logger.info(
        "PostgreSQL pool config: pool_size=%d, max_overflow=%d, recycle=%ds",
        pool_size, max_overflow, pool_recycle
    )
    
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,  # Verify connections before use
        future=True,
    )


def _initialize_engine() -> Engine:
    """Initialize the database engine with retry support.
    
    Retries connection with exponential backoff.
    
    Environment Variables:
        DB_CONNECT_RETRIES: Number of retry attempts (default: 3)
        DB_RETRY_DELAY: Initial delay between retries in seconds (default: 1.0)
    """
    masked_url = _mask_db_url(DATABASE_URL)
    env = os.getenv("ENVIRONMENT", "production").lower()
    logger.info("ENVIRONMENT=%s | DATABASE_URL=%s", env, masked_url)
    
    # Retry configuration
    max_retries = int(os.getenv("DB_CONNECT_RETRIES", "3"))
    base_delay = float(os.getenv("DB_RETRY_DELAY", "1.0"))
    
    last_error: Exception | None = None
    
    for attempt in range(1, max_retries + 1):
        try:
            engine = _create_engine(DATABASE_URL)
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


def get_api_read_session() -> Generator[Session, None, None]:
    """Yield a read-only session for external API handlers."""
    session = SessionLocal()
    session.info["read_only_api"] = True
    try:
        if session.bind and session.bind.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
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
    from app.env_config import validate_api_secrets_at_startup
    from app.sync import register_sync_events

    validate_api_secrets_at_startup()

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
            import secrets
            default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", secrets.token_urlsafe(16))
            admin_user = User.create_user("admin", default_password, role="admin")
            session.add(admin_user)
            session.commit()
            logger.info("Created default admin user (username: admin, password: %s)", default_password)
            logger.warning("CHANGE THE DEFAULT ADMIN PASSWORD IMMEDIATELY")
    except Exception as e:
        logger.error("Error creating admin user: %s", e)
        session.rollback()
    finally:
        session.close()

    # Seed default PayConfig and FrequencyPlan if empty
    session = SessionLocal()
    try:
        from app.models import PayConfig, FrequencyPlan
        if session.query(PayConfig).count() == 0:
            session.add(PayConfig(
                name="Default",
                pay_days='[7, 14, 21, "eom"]',
                currency="USD",
                is_default=True,
            ))
            session.commit()
            logger.info("Seeded default pay config")
        if session.query(FrequencyPlan).count() == 0:
            session.add_all([
                FrequencyPlan(name="weekly", pay_day_indices="[0, 1, 2, 3]", display_name="Weekly (4x/month)"),
                FrequencyPlan(name="biweekly", pay_day_indices="[1, 3]", display_name="Biweekly (2x/month)"),
                FrequencyPlan(name="monthly", pay_day_indices="[3]", display_name="Monthly (1x/month)"),
            ])
            session.commit()
            logger.info("Seeded default frequency plans")
    except Exception as e:
        logger.error("Error seeding pay config: %s", e)
        session.rollback()
    finally:
        session.close()

    from app.sync import register_sync_events

    register_sync_events()

    session = SessionLocal()
    try:
        from app.models import SyncState

        if session.get(SyncState, 1) is None:
            session.add(SyncState(id=1, revision=0))
            session.commit()
    except Exception as e:
        logger.error("Error seeding sync_state: %s", e)
        session.rollback()
    finally:
        session.close()

