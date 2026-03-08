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
from app.security import (
    record_login_attempt,
    is_account_locked,
    increment_failed_login,
    reset_failed_login,
)

logger = logging.getLogger(__name__)

_SESSION_SECRET = os.getenv("SESSION_SECRET", os.getenv("SECRET_KEY", "change-me-in-production"))
if os.getenv("ENVIRONMENT", "development").lower() == "production" and _SESSION_SECRET == "change-me-in-production":
    raise RuntimeError("SESSION_SECRET or SECRET_KEY must be set in production; refusing to start with default secret.")
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
        
        # Get updated failed attempt count
        user = db.query(User).filter(User.username == username).first()
        failed_count = user.failed_login_count if user else 0
        attempts_remaining = max(0, 5 - failed_count)
        
        # Create error message with attempt counter
        error_msg = "Invalid username or password"
        if attempts_remaining > 0:
            error_msg += f" ({attempts_remaining} attempt{'s' if attempts_remaining != 1 else ''} remaining)"
        
        # Return login page with error and attempt count
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": error_msg,
                "attempts_remaining": attempts_remaining,
                "failed_count": failed_count,
            },
            status_code=401,
        )
    
    # Successful login - reset failed counter and record attempt
    reset_failed_login(db, username)
    record_login_attempt(db, username, True, client_ip, user_agent)
    
    # Determine safe redirect target
    redirect_to = next or request.query_params.get("next") or "/dashboard"
    # Prevent open redirects: only allow same-site paths
    if not isinstance(redirect_to, str) or "://" in redirect_to or not redirect_to.startswith("/"):
        redirect_to = "/dashboard"

    # Set signed session cookie and redirect
    response = RedirectResponse(url=redirect_to, status_code=303)
    is_production = os.getenv("ENVIRONMENT", "production").lower() == "production"
    signed_token = _signer.dumps(user.id)
    response.set_cookie(
        key="session",
        value=signed_token,
        httponly=True,
        path="/",
        secure=is_production,
        samesite="lax",
        max_age=_SESSION_MAX_AGE,
    )
    return response



@router.get("/logout")
def logout():
    """Handle logout — clear session cookie."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response


def get_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    """Dependency to get current authenticated user from signed session cookie."""
    token = request.cookies.get("session")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = _signer.loads(token, max_age=_SESSION_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired")
    except BadSignature:
        logger.warning("Invalid session signature from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user is admin."""
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
