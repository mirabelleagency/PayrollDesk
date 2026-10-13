"""Authentication routes and session management."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from app.database import get_session
from app.auth import User
from app.dependencies import templates
from app.env_config import current_environment, is_development_environment, is_test_environment
from app.security import (
    safe_redirect_path,
    record_login_attempt,
    is_account_locked,
    increment_failed_login,
    reset_failed_login,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRET = "change-me-in-production"
_SESSION_SECRET = (os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY") or "").strip()
if not _SESSION_SECRET or _SESSION_SECRET == _PLACEHOLDER_SECRET:
    # Only an explicitly dev/test environment may run on a known secret. This
    # used to treat a *missing* ENVIRONMENT as development, so a deploy without
    # ENVIRONMENT or SESSION_SECRET signed sessions with the public default and
    # anyone could forge an admin cookie.
    if not (is_development_environment() or is_test_environment()):
        raise RuntimeError(
            "SESSION_SECRET (or SECRET_KEY) must be set; refusing to start with no "
            f"session secret when ENVIRONMENT={current_environment()!r}."
        )
    _SESSION_SECRET = "dev-session-secret-not-for-production-use"
_SESSION_MAX_AGE = 86400  # 24 hours
_signer = URLSafeTimedSerializer(_SESSION_SECRET, salt="user-session")

router = APIRouter(tags=["Auth"])


@router.get("/login")
def login_page(request: Request):
    """Render login page, optionally preserving a next destination."""
    next_param = request.query_params.get("next")
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request, "next": next_param},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(default=None),
    db: Session = Depends(get_session),
):
    """Handle login form submission with rate limiting and account lockout."""
    # Get client IP address
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Check if account is locked
    locked, lock_reason = is_account_locked(db, username)
    if locked:
        record_login_attempt(db, username, False, client_ip, user_agent)
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": f"Account locked due to too many failed login attempts. {lock_reason}",
            },
            status_code=403,
        )
    
    # Find user
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.verify_password(password):
        # Record failed attempt
        increment_failed_login(db, username)
        record_login_attempt(db, username, False, client_ip, user_agent)
        
        
        # Same message whether or not the username exists. The old "(N attempts
        # remaining)" counted down only for real accounts (unknown names always
        # said 5), which told anyone which usernames exist.
        error_msg = "Invalid username or password"
        
        # Return login page with the error
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": error_msg,
            },
            status_code=401,
        )
    
    # Successful login - reset failed counter and record attempt
    reset_failed_login(db, username)
    record_login_attempt(db, username, True, client_ip, user_agent)
    
    # Determine safe redirect target
    # Prevent open redirects: only allow same-site paths
    redirect_to = safe_redirect_path(next or request.query_params.get("next"), "/dashboard")

    # Set signed session cookie and redirect
    response = RedirectResponse(url=redirect_to, status_code=303)
    set_session_cookie(response, user)
    return response


def set_session_cookie(response, user: User) -> None:
    """Sign a session for ``user`` at their current session version."""
    is_production = os.getenv("ENVIRONMENT", "production").lower() == "production"
    signed_token = _signer.dumps({"u": user.id, "v": user.session_version or 0})
    response.set_cookie(
        key="session",
        value=signed_token,
        httponly=True,
        path="/",
        secure=is_production,
        samesite="lax",
        max_age=_SESSION_MAX_AGE,
    )


def _user_for_token(token: str | None, db: Session) -> User | None:
    """The user a session cookie belongs to, or None if it is missing or was
    revoked. Raises SignatureExpired / BadSignature for the caller to report."""
    if not token:
        return None
    payload = _signer.loads(token, max_age=_SESSION_MAX_AGE)
    if isinstance(payload, dict):
        user_id, version = payload.get("u"), payload.get("v")
    else:
        # Cookies issued before session versions carried just the user id;
        # they stay valid until the user's first logout or password change.
        user_id, version = payload, 0
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or (user.session_version or 0) != version:
        return None
    return user



@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_session)):
    """Log out: end the session server-side (every device), then clear the cookie.

    Only clearing the cookie left a copied or stolen cookie valid for up to 24h.
    """
    try:
        user = _user_for_token(request.cookies.get("session"), db)
    except (SignatureExpired, BadSignature):
        user = None
    if user:
        user.end_all_sessions()
        db.commit()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response


def get_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    """Dependency to get current authenticated user from signed session cookie."""
    token = request.cookies.get("session")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user = _user_for_token(token, db)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired")
    except BadSignature:
        logger.warning("Invalid session signature from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=401, detail="Invalid session")

    if not user:
        raise HTTPException(status_code=401, detail="Session ended")

    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user is admin."""
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
