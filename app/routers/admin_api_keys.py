"""Admin routes for API key management."""
from __future__ import annotations

from datetime import datetime

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
        parsed_expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M") if expires_at else None
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
