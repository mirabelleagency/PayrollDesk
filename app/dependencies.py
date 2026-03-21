"""Shared FastAPI dependencies."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.core.formatting import format_display_date, format_display_datetime
from app import __version__
from app.database import get_session
from app.icons import icon
from app.security import generate_csrf_token, validate_csrf_token

TEMPLATES_PATH = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_PATH))


def _format_money(value) -> str:
    """Format numeric values with thousand separators and two decimals."""

    if value in (None, ""):
        decimal_value = Decimal("0")
    else:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return str(value)

    decimal_value = decimal_value.quantize(Decimal("0.01"))
    return f"{decimal_value:,.2f}"


def _format_display_date(value) -> str:
    """Expose consistent mm/dd/yyyy formatting to templates."""

    return format_display_date(value)


def _format_display_datetime(value) -> str:
    """Expose consistent mm/dd/yyyy hh:mm AM/PM formatting to templates."""

    return format_display_datetime(value)


templates.env.filters["money"] = _format_money
templates.env.filters["display_date"] = _format_display_date
templates.env.filters["display_datetime"] = _format_display_datetime

# Global template variables
templates.env.globals["APP_VERSION"] = __version__
templates.env.globals["APP_NAME"] = "Payroll Desk"
templates.env.globals["icon"] = icon


def _csrf_token(request: Request) -> str:
    """Return a raw CSRF token string for use in meta tags / JS."""
    session_cookie = request.cookies.get("session", "")
    if not session_cookie:
        return ""
    return generate_csrf_token(session_cookie)


templates.env.globals["csrf_token"] = _csrf_token


# ---------------------------------------------------------------------------
# CSRF verification paths to skip
# ---------------------------------------------------------------------------
_CSRF_EXEMPT_PATHS = {"/health", "/health/db", "/login"}


async def verify_csrf(request: Request) -> None:
    """FastAPI dependency that validates CSRF tokens on POST/PUT/DELETE/PATCH."""
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return

    path = request.url.path.rstrip("/")
    if path in _CSRF_EXEMPT_PATHS:
        return

    # API endpoints protected by Origin/Referer middleware; skip token check
    if path.startswith("/admin/api/") or path.startswith("/api/"):
        return

    session_cookie = request.cookies.get("session", "")
    if not session_cookie:
        return  # unauthenticated – auth dependency will reject later

    form_data = await request.form()
    token = form_data.get("_csrf_token", "")

    if not validate_csrf_token(token, session_cookie):
        raise HTTPException(status_code=403, detail="CSRF validation failed")

get_db = get_session
