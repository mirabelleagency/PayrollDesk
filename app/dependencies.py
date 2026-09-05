"""Shared FastAPI dependencies."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from starlette.requests import Request
from starlette.templating import Jinja2Templates as StarletteJinja2Templates

from app.core.formatting import format_display_date, format_display_datetime
from app import __version__
from app.database import get_session

TEMPLATES_PATH = Path(__file__).parent / "templates"


class Jinja2Templates(StarletteJinja2Templates):
    """Support legacy TemplateResponse(name, context) calls on Starlette 1.x."""

    def TemplateResponse(self, request_or_name, name_or_context=None, context=None, **kwargs):
        if isinstance(request_or_name, str):
            name = request_or_name
            ctx = name_or_context or {}
            request = ctx.get("request")
            if request is None:
                raise ValueError("Template context must include 'request'")
            return super().TemplateResponse(request, name, ctx, **kwargs)
        return super().TemplateResponse(request_or_name, name_or_context, context, **kwargs)


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

get_db = get_session
