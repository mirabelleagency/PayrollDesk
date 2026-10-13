"""Admin routes for API key management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.keys import create_api_key_record, list_api_keys, revoke_api_key
from app.api.scopes import V2_RESOURCES, normalize_scopes
from app.auth import User
from app.database import get_session
from app.dependencies import templates
from app import crud
from app.models import ApiKey
from app.routers.auth import get_admin_user
from app.time_utils import utc_now

router = APIRouter(prefix="/admin", tags=["Admin"])

# What each v2 resource hands out, in the words shown on the create form.
# `sensitive` marks resources carrying personal or payment details.
SCOPE_RESOURCES = {
    "models": ("Models", "Legal names, codes, pay rates, payment method, crypto wallets", True),
    "payouts": ("Payouts", "Payout amounts, dates, status, notes, recipient wallet", True),
    "adhoc-payments": ("Ad hoc payments", "One-off payments, amounts, status, notes", True),
    "adjustments": ("Pay adjustments", "Pay-rate changes and their notes", True),
    "advances": ("Advances", "Advances given to models, balances, notes", True),
    "advance-repayments": ("Advance repayments", "Repayments made against advances", False),
    "advance-allocations": ("Advance allocations", "Which payouts repaid which advances", False),
    "schedule-runs": ("Schedule runs", "When payroll was generated and for which months", False),
    "validation-issues": ("Validation issues", "Data problems flagged during payroll generation", False),
}
assert set(SCOPE_RESOURCES) == set(V2_RESOURCES)

SCOPE_CHOICES = [
    {"scope": f"v2:{resource}", "label": label, "description": description, "sensitive": sensitive}
    for resource, (label, description, sensitive) in SCOPE_RESOURCES.items()
]

SCOPE_PRESETS = {
    "full": ["v2:*"],
    "salary": ["v2:models", "v2:payouts", "v2:adhoc-payments"],
}

STALE_AFTER_DAYS = 90


def _scope_chips(scopes: list[str]) -> list[dict]:
    chips = []
    for scope in scopes:
        version, _, resource = scope.partition(":")
        if resource == "*":
            label = "Full read access"
        else:
            label = SCOPE_RESOURCES.get(resource, (resource,))[0]
        if version == "v1":
            chips.append({"label": f"{label} (v1)", "kind": "legacy", "scope": scope})
        else:
            chips.append({"label": label, "kind": "full" if resource == "*" else "normal", "scope": scope})
    return chips


def _relative(value: datetime | None, now: datetime) -> str | None:
    if value is None:
        return None
    seconds = (now - value).total_seconds()
    future = seconds < 0
    seconds = abs(seconds)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            count = int(seconds // size)
            text = f"{count} {unit}{'' if count == 1 else 's'}"
            return f"in {text}" if future else f"{text} ago"
    return "just now"


def _key_row(key: ApiKey, now: datetime) -> dict:
    scopes = key.scope_list()
    if key.revoked_at:
        status = "revoked"
    elif key.expires_at and key.expires_at <= now:
        status = "expired"
    else:
        status = "active"
    last_activity = key.last_used_at or key.created_at
    return {
        "key": key,
        "status": status,
        "chips": _scope_chips(scopes),
        "legacy": any(scope.startswith("v1:") for scope in scopes),
        "last_used": _relative(key.last_used_at, now),
        "expires": _relative(key.expires_at, now),
        "stale": status == "active"
        and last_activity is not None
        and (now - last_activity).days >= STALE_AFTER_DAYS,
    }


def _api_base_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    # TLS ends at the hosting proxy, so the app sees http:// for an https site.
    if base.startswith("http://") and request.url.hostname not in ("localhost", "127.0.0.1", "testserver"):
        base = "https://" + base[len("http://") :]
    return base


def _render_page(request, admin, keys, **extra):
    now = utc_now()
    rows = [_key_row(key, now) for key in keys]
    return templates.TemplateResponse(
        request,
        "admin/api_keys.html",
        {
            "request": request,
            "user": admin,
            "active_keys": [row for row in rows if row["status"] == "active"],
            "inactive_keys": [row for row in rows if row["status"] != "active"],
            "scope_choices": SCOPE_CHOICES,
            "api_base_url": _api_base_url(request),
            "new_plaintext_key": None,
            "form": {},
            **extra,
        },
    )


@router.get("/api-keys")
def list_api_keys_page(
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    return _render_page(request, admin, list_api_keys(db))


def _parse_expiry(value: str | None) -> datetime | None:
    """An expiry as naive UTC, which is how keys are stored and compared.

    Accepts ISO 8601. A value with an offset ("2026-11-01T17:00+08:00") is
    converted to UTC; a bare value is taken as UTC. It used to be parsed as a
    bare local time and stored as if it were UTC, so a key set to expire at
    17:00 in UTC+8 lived until 01:00 the next day.
    """
    if not value or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("Expiry must be an ISO date-time, e.g. 2026-11-01T17:00+08:00") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    if parsed <= utc_now():
        raise ValueError("Expiry must be in the future.")
    return parsed


def _requested_scopes(preset: str | None, scopes: list[str]) -> list[str]:
    if preset and preset != "custom":
        if preset not in SCOPE_PRESETS:
            raise ValueError(f"Unknown access level: {preset}")
        return list(SCOPE_PRESETS[preset])
    if not scopes:
        if preset == "custom":
            raise ValueError("Pick at least one resource for custom access.")
        return list(SCOPE_PRESETS["full"])
    if any(scope.strip().startswith("v1:") for scope in scopes):
        raise ValueError("The v1 API has been removed; use v2 scopes.")
    return normalize_scopes(scopes)


@router.post("/api-keys")
def create_api_key(
    request: Request,
    name: str = Form(...),
    preset: str | None = Form(default=None),
    scopes: list[str] = Form(default=[]),
    expires_at: str | None = Form(default=None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    try:
        parsed_expiry = _parse_expiry(expires_at)
        record, plaintext = create_api_key_record(
            db,
            name=name,
            created_by=admin.username,
            scopes=_requested_scopes(preset, scopes),
            expires_at=parsed_expiry,
        )
        crud.log_admin_action(
            db,
            admin.id,
            "create_api_key",
            {"key_id": record.id, "name": record.name, "prefix": record.key_prefix},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        response = _render_page(
            request,
            admin,
            list_api_keys(db),
            error=str(exc),
            form={"name": name, "preset": preset or "full", "scopes": scopes},
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = _render_page(
        request,
        admin,
        list_api_keys(db),
        message=f"API key '{record.name}' created.",
        new_plaintext_key=plaintext,
        new_key_name=record.name,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/api-keys/{key_id}/rotate")
def rotate_api_key_route(
    request: Request,
    key_id: int,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Issue a replacement with the same name, scopes and expiry.

    The old key stays active, so the client can switch over before it is
    revoked; rotating never causes downtime on its own.
    """
    old = db.get(ApiKey, key_id)
    if old is None:
        raise HTTPException(status_code=404, detail="API key not found")
    now = utc_now()
    if old.revoked_at or (old.expires_at and old.expires_at <= now):
        raise HTTPException(status_code=400, detail="Only active keys can be rotated")
    if not any(scope.startswith("v2:") for scope in old.scope_list()):
        raise HTTPException(status_code=400, detail="v1 keys cannot be rotated; create a v2 key instead")

    record, plaintext = create_api_key_record(
        db,
        name=old.name,
        created_by=admin.username,
        scopes=old.scope_list(),
        expires_at=old.expires_at,
    )
    crud.log_admin_action(
        db,
        admin.id,
        "rotate_api_key",
        {
            "key_id": record.id,
            "replaces_key_id": old.id,
            "name": record.name,
            "prefix": record.key_prefix,
        },
    )
    db.commit()

    response = _render_page(
        request,
        admin,
        list_api_keys(db),
        message=(
            f"Replacement for '{old.name}' created. The old key ({old.key_prefix}…) still works: "
            "revoke it once the client is using the new one."
        ),
        new_plaintext_key=plaintext,
        new_key_name=record.name,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/api-keys/{key_id}/revoke")
def revoke_api_key_route(
    request: Request,
    key_id: int,
    revoke_reason: str | None = Form(default=None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    record = revoke_api_key(
        db,
        key_id,
        revoked_by=admin.username,
        revoke_reason=(revoke_reason or "").strip() or None,
    )
    if record is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="API key not found")

    crud.log_admin_action(
        db,
        admin.id,
        "revoke_api_key",
        {"key_id": record.id, "name": record.name, "prefix": record.key_prefix},
    )
    db.commit()
    return RedirectResponse(url="/admin/api-keys", status_code=303)
