"""Admin routes for API key management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.keys import create_api_key_record, list_api_keys, revoke_api_key
from app.api.scopes import V1_RESOURCES, V2_RESOURCES, normalize_scopes
from app.auth import User
from app.database import get_session
from app.dependencies import templates
from app import crud
from app.routers.auth import get_admin_user

router = APIRouter(prefix="/admin", tags=["Admin"])

SCOPE_CHOICES = [f"v1:{r}" for r in V1_RESOURCES] + [f"v2:{r}" for r in V2_RESOURCES] + ["v1:*", "v2:*"]


def _render_page(request, admin, keys, **extra):
    return templates.TemplateResponse(
        request,
        "admin/api_keys.html",
        {
            "request": request,
            "user": admin,
            "api_keys": keys,
            "scope_choices": SCOPE_CHOICES,
            "new_plaintext_key": None,
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
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("Expiry must be an ISO date-time, e.g. 2026-11-01T17:00+08:00") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@router.post("/api-keys")
def create_api_key(
    request: Request,
    name: str = Form(...),
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
            scopes=normalize_scopes(scopes or ["v2:*"]),
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
        message=(
            f"API key '{record.name}' created. Copy the secret below — it will not be shown again. "
            "v2:* grants read access to legal names, notes, and wallet addresses."
        ),
        new_plaintext_key=plaintext,
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
