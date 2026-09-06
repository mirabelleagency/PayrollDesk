"""DB-backed API rate limiting."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.env_config import is_development_environment, is_test_environment

RATE_LIMIT_PER_MINUTE = 120
WINDOW_SECONDS = 60


def _rate_secret() -> str:
    secret = os.getenv("API_RATE_SECRET", "").strip()
    if secret:
        if len(secret) < 32 and not (is_development_environment() or is_test_environment()):
            raise RuntimeError("API_RATE_SECRET must be at least 32 characters outside dev/test.")
        return secret
    if is_development_environment() or is_test_environment():
        return "dev-rate-secret-not-for-production-use-32chars"
    raise RuntimeError("API_RATE_SECRET is required outside development/test.")


def _bucket_hash(kind: str, identifier: str) -> str:
    payload = f"{kind}:{identifier}".encode("utf-8")
    return hmac.new(_rate_secret().encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _window_start(now: float | None = None) -> int:
    ts = int(now or time.time())
    return ts - (ts % WINDOW_SECONDS)


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int | None = None


def _increment_bucket(session: Session, bucket_hash: str, window_start: int) -> int:
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        row = session.execute(
            text(
                """
                INSERT INTO api_rate_windows (bucket_hash, window_start_epoch, request_count)
                VALUES (:hash, :start, 1)
                ON CONFLICT (bucket_hash, window_start_epoch)
                DO UPDATE SET request_count = api_rate_windows.request_count + 1
                RETURNING request_count
                """
            ),
            {"hash": bucket_hash, "start": window_start},
        ).scalar_one()
    else:
        session.execute(
            text(
                """
                INSERT INTO api_rate_windows (bucket_hash, window_start_epoch, request_count)
                VALUES (:hash, :start, 1)
                ON CONFLICT(bucket_hash, window_start_epoch)
                DO UPDATE SET request_count = request_count + 1
                """
            ),
            {"hash": bucket_hash, "start": window_start},
        )
        row = session.execute(
            text(
                "SELECT request_count FROM api_rate_windows WHERE bucket_hash = :hash AND window_start_epoch = :start"
            ),
            {"hash": bucket_hash, "start": window_start},
        ).scalar_one()
    return int(row)


def _cleanup_old_windows(session: Session, current_window: int) -> None:
    cutoff = current_window - (2 * WINDOW_SECONDS)
    session.execute(
        text("DELETE FROM api_rate_windows WHERE window_start_epoch < :cutoff LIMIT 100"),
        {"cutoff": cutoff // WINDOW_SECONDS * WINDOW_SECONDS},
    )


def check_rate_limit(kind: str, identifier: str) -> RateLimitResult:
    window = _window_start()
    bucket = _bucket_hash(kind, identifier)
    session = SessionLocal()
    try:
        count = _increment_bucket(session, bucket, window)
        if count == 1:
            try:
                _cleanup_old_windows(session, window)
            except Exception:
                pass
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    finally:
        session.close()

    if count > RATE_LIMIT_PER_MINUTE:
        retry_after = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        return RateLimitResult(allowed=False, retry_after=max(1, retry_after))
    return RateLimitResult(allowed=True)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_ip_rate_limit(request: Request) -> None:
    result = check_rate_limit("ip", client_ip(request))
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.retry_after or WINDOW_SECONDS)},
        )


def enforce_key_rate_limit(key_id: int) -> None:
    result = check_rate_limit("key", str(key_id))
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.retry_after or WINDOW_SECONDS)},
        )
