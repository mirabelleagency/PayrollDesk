"""Security utilities for rate limiting and account lockout."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth import User
from app.models import LoginAttempt
from app.core.formatting import format_display_datetime

# CSRF secret – reuse the same session secret so no extra config is needed
_CSRF_SECRET = os.getenv("SESSION_SECRET", os.getenv("SECRET_KEY", "change-me-in-production"))


def generate_csrf_token(session_cookie: str) -> str:
    """Generate a CSRF token cryptographically bound to the session cookie."""
    return hmac.new(
        _CSRF_SECRET.encode("utf-8"),
        session_cookie.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_csrf_token(token: str, session_cookie: str) -> bool:
    """Validate a CSRF token against the session cookie."""
    if not token or not session_cookie:
        return False
    expected = generate_csrf_token(session_cookie)
    return hmac.compare_digest(token, expected)

# Configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW_MINUTES = 15


def record_login_attempt(
    db: Session,
    username: str,
    success: bool,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record a login attempt in the database."""
    attempt = LoginAttempt(
        username=username,
        success=success,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(attempt)
    db.commit()


def get_failed_attempts_count(
    db: Session,
    username: str,
    minutes: int = RATE_LIMIT_WINDOW_MINUTES,
) -> int:
    """Get count of failed login attempts in the last N minutes."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    stmt = select(LoginAttempt).where(
        LoginAttempt.username == username,
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= cutoff_time,
    )
    
    attempts = db.execute(stmt).scalars().all()
    return len(attempts)


def is_account_locked(db: Session, username: str) -> tuple[bool, str | None]:
    """
    Check if account is locked.
    Returns (is_locked, reason_message)
    """
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return False, None
    
    # Check if account is permanently locked by admin
    if user.is_locked:
        if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            formatted = format_display_datetime(user.locked_until)
            return True, f"Account is locked until {formatted}"
        else:
            # Auto-unlock if lockout period has passed
            user.is_locked = False
            user.locked_until = None
            user.failed_login_count = 0
            db.add(user)
            db.commit()
            return False, None
    
    return False, None


def lock_account(
    db: Session,
    username: str,
    duration_minutes: int = LOCKOUT_DURATION_MINUTES,
) -> None:
    """Lock a user account after too many failed attempts."""
    user = db.query(User).filter(User.username == username).first()
    
    if user:
        user.is_locked = True
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        user.failed_login_count = 0  # Reset counter
        db.add(user)
        db.commit()


def increment_failed_login(db: Session, username: str) -> None:
    """Increment failed login counter for a user."""
    user = db.query(User).filter(User.username == username).first()
    
    if user:
        user.failed_login_count += 1
        user.last_failed_login = datetime.now(timezone.utc)
        db.add(user)
        db.commit()
        
        # Lock account if max attempts reached
        if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
            lock_account(db, username)


def reset_failed_login(db: Session, username: str) -> None:
    """Reset failed login counter after successful login."""
    user = db.query(User).filter(User.username == username).first()
    
    if user:
        user.failed_login_count = 0
        user.last_failed_login = None
        db.add(user)
        db.commit()


def unlock_account(db: Session, username: str) -> None:
    """Manually unlock an account (admin only)."""
    user = db.query(User).filter(User.username == username).first()
    
    if user:
        user.is_locked = False
        user.locked_until = None
        user.failed_login_count = 0
        user.last_failed_login = None
        db.add(user)
        db.commit()


def get_recent_login_attempts(
    db: Session,
    username: str,
    limit: int = 10,
) -> list[LoginAttempt]:
    """Get recent login attempts for a user."""
    stmt = (
        select(LoginAttempt)
        .where(LoginAttempt.username == username)
        .order_by(LoginAttempt.attempted_at.desc())
        .limit(limit)
    )
    
    return db.execute(stmt).scalars().all()


class PasswordValidator:
    """Simple password strength validator for user updates."""

    @staticmethod
    def validate(password: str) -> tuple[bool, str]:
        if not password:
            return False, "Password cannot be empty"
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        has_letter = any(char.isalpha() for char in password)
        has_digit = any(char.isdigit() for char in password)

        if not has_letter or not has_digit:
            return False, "Password must include at least one letter and one number"

        return True, ""
