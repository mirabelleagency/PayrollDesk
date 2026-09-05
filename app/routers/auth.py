"""Authentication routes and session management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.auth import User
from app.dependencies import templates
from app.auth_session import bump_session_version, store_session_user, validate_session_user
from app.security import (
    record_login_attempt,
    is_account_locked,
    increment_failed_login,
    reset_failed_login,
)

router = APIRouter(tags=["Auth"])


@router.get("/login")
def login_page(request: Request):
    """Render login page, optionally preserving a next destination."""
    next_param = request.query_params.get("next")
    return templates.TemplateResponse("auth/login.html", {"request": request, "next": next_param})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(default=None),
    db: Session = Depends(get_session),
):
    """Handle login form submission with rate limiting and account lockout."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    locked, lock_reason = is_account_locked(db, username)
    if locked:
        record_login_attempt(db, username, False, client_ip, user_agent)
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": f"Account locked due to too many failed login attempts. {lock_reason}",
            },
            status_code=403,
        )

    user = db.query(User).filter(User.username == username).first()

    if not user or not user.verify_password(password):
        increment_failed_login(db, username)
        record_login_attempt(db, username, False, client_ip, user_agent)

        user = db.query(User).filter(User.username == username).first()
        failed_count = user.failed_login_count if user else 0
        attempts_remaining = max(0, 5 - failed_count)

        error_msg = "Invalid username or password"
        if attempts_remaining > 0:
            error_msg += f" ({attempts_remaining} attempt{'s' if attempts_remaining != 1 else ''} remaining)"

        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": error_msg,
                "attempts_remaining": attempts_remaining,
                "failed_count": failed_count,
            },
            status_code=401,
        )

    reset_failed_login(db, username)
    record_login_attempt(db, username, True, client_ip, user_agent)

    redirect_to = next or request.query_params.get("next") or "/dashboard"
    if not isinstance(redirect_to, str) or "://" in redirect_to or not redirect_to.startswith("/"):
        redirect_to = "/dashboard"

    store_session_user(request, user)

    return RedirectResponse(url=redirect_to, status_code=303)


def get_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    """Dependency to get current authenticated user from signed session."""
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.is_locked:
        raise HTTPException(status_code=401, detail="Account locked")

    if not validate_session_user(request, user):
        raise HTTPException(status_code=401, detail="Session expired")

    return user


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Handle logout — bump session version and clear cookie."""
    bump_session_version(db, user)
    db.commit()
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user is admin."""
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
