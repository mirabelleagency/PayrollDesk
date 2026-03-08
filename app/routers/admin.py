"""Admin routes for user and data administration."""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine.url import make_url
import os

from app import crud
from app.auth import User
from app.database import get_session, engine, DATABASE_URL
from app.dependencies import templates
from app.models import PayConfig, FrequencyPlan
from app.routers.auth import get_admin_user
from app.security import unlock_account, PasswordValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
def list_users(
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """List all users (admin only)."""
    users = db.query(User).all()
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "request": request,
            "users": users,
            "user": admin,
        },
    )


@router.get("/users/new")
def new_user_form(
    request: Request,
    admin: User = Depends(get_admin_user),
):
    """Show new user creation form (admin only)."""
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "request": request,
            "action": "create",
            "user": admin,
        },
    )


@router.post("/users/new")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Create a new user (admin only)."""
    # Check if username already exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "request": request,
                "action": "create",
                "error": "Username already exists",
                "user": admin,
            },
            status_code=400,
        )
    
    # Validate role
    if role not in ["admin", "user"]:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "request": request,
                "action": "create",
                "error": "Invalid role",
                "user": admin,
            },
            status_code=400,
        )
    
    new_user = User.create_user(username, password, role=role)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Handle unique constraint violation
        if "username" in str(e):
            return templates.TemplateResponse(
                request,
                "admin/user_form.html",
                {
                    "request": request,
                    "action": "create",
                    "error": "Username already exists",
                    "user": admin,
                },
                status_code=400,
            )
        raise
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/users/{user_id}/edit")
def edit_user_form(
    user_id: int,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Show user edit form (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "request": request,
            "action": "edit",
            "form_user": user,
            "user": admin,
        },
    )


@router.post("/users/{user_id}/edit")
def update_user(
    user_id: int,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Update user role (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from modifying their own role
    if user.id == admin.id:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "request": request,
                "action": "edit",
                "form_user": user,
                "error": "Cannot modify your own role",
                "user": admin,
            },
            status_code=400,
        )
    
    if role not in ["admin", "user"]:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "request": request,
                "action": "edit",
                "form_user": user,
                "error": "Invalid role",
                "user": admin,
            },
            status_code=400,
        )
    
    user.role = role
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Reset user password (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_valid, error_msg = PasswordValidator.validate(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    user.password_hash = User.hash_password(new_password)
    # Auto-unlock the account if it was locked
    if user.is_locked:
        unlock_account(db, user.username)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/unlock")
def unlock_user_account(
    user_id: int,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Unlock a locked user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if account is actually locked
    if not user.is_locked:
        raise HTTPException(status_code=400, detail="Account is not locked")
    
    # Unlock the account
    unlock_account(db, user.username)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Delete user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting their own account
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


# --- Data purge endpoints ---------------------------------------------------

@router.get("/models/{model_id}/purge")
def purge_model_preview(
    model_id: int,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Show a confirmation page with a dry-run summary before purging a model."""
    impact = crud.get_model_purge_impact(db, model_id)
    return templates.TemplateResponse(
        request,
        "admin/purge_confirm.html",
        {
            "request": request,
            "user": admin,
            "impact": impact,
        },
    )


@router.post("/models/{model_id}/purge")
def purge_model_execute(
    model_id: int,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Execute the hard purge of a model and related records (admin only)."""
    try:
        impact = crud.purge_model_hard(db, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Log admin action
    try:
        crud.log_admin_action(db, admin.id, "purge_model", {"impact": impact})
    except Exception:
        logger.exception("Audit log failed for purge_model")

    # Redirect to models list with a lightweight success note in query
    code = impact.get("model_code", "")
    return RedirectResponse(url=f"/models?purged={code}", status_code=303)


# --- Admin Settings & Maintenance ------------------------------------------

@router.get("/settings")
def admin_settings(
    request: Request,
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    pay_config = crud.get_pay_config(db)
    frequency_plans = crud.list_active_frequency_plans(db)
    # Also get inactive plans
    all_plans = db.query(FrequencyPlan).order_by(FrequencyPlan.name).all()

    return templates.TemplateResponse(
        request,
        "admin/settings.html",
        {
            "request": request,
            "user": admin,
            "message": message,
            "error": error,
            "pay_config": pay_config,
            "frequency_plans": all_plans,
        },
    )


@router.post("/settings/pay-config")
def update_pay_config(
    request: Request,
    config_name: str = Form("Default"),
    pay_days: str = Form(...),
    currency: str = Form("USD"),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Update the default pay config."""
    try:
        parsed = json.loads(pay_days)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("pay_days must be a non-empty list")
        # Validate each entry is int or "eom"
        for item in parsed:
            if item == "eom":
                continue
            if not isinstance(item, int) or item < 1 or item > 31:
                raise ValueError(f"Invalid pay day: {item}. Must be 1-31 or 'eom'.")
    except json.JSONDecodeError:
        return RedirectResponse(
            url="/admin/settings?error=Invalid+JSON+for+pay+days", status_code=303
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/admin/settings?error={str(e)}", status_code=303
        )

    config = crud.get_pay_config(db)
    if config:
        config.name = config_name.strip()
        config.pay_days = json.dumps(parsed)
        config.currency = currency.upper().strip()
    else:
        config = PayConfig(
            name=config_name.strip(),
            pay_days=json.dumps(parsed),
            currency=currency.upper().strip(),
            is_default=True,
        )
        db.add(config)
    db.commit()

    try:
        crud.log_admin_action(db, admin.id, "update_pay_config", {"pay_days": parsed, "currency": currency})
    except Exception:
        logger.exception("Audit log failed for update_pay_config")

    return RedirectResponse(url="/admin/settings?message=Pay+config+updated", status_code=303)


@router.post("/settings/frequency-plans/{plan_id}")
def update_frequency_plan(
    request: Request,
    plan_id: int,
    display_name: str = Form(...),
    pay_day_indices: str = Form(...),
    is_active: str | None = Form(None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Update a frequency plan."""
    plan = db.get(FrequencyPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Frequency plan not found")

    try:
        parsed = json.loads(pay_day_indices)
        if not isinstance(parsed, list):
            raise ValueError("pay_day_indices must be a list")
    except (json.JSONDecodeError, ValueError) as e:
        return RedirectResponse(
            url=f"/admin/settings?error=Invalid+indices:+{e}", status_code=303
        )

    plan.display_name = display_name.strip()
    plan.pay_day_indices = json.dumps(parsed)
    plan.is_active = is_active is not None
    db.commit()

    return RedirectResponse(url="/admin/settings?message=Frequency+plan+updated", status_code=303)


@router.post("/maintenance/cleanup-empty-runs")
def maintenance_cleanup_empty_runs(
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    result = crud.cleanup_empty_runs(db)
    try:
        crud.log_admin_action(db, admin.id, "cleanup_empty_runs", result)
    except Exception:
        logger.exception("Audit log failed for cleanup_empty_runs")
    msg = f"Deleted {result['deleted_runs']} empty run(s)."
    return RedirectResponse(url=f"/admin/settings?message={msg}", status_code=303)


@router.post("/maintenance/cleanup-orphans")
def maintenance_cleanup_orphans(
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    result = crud.cleanup_orphans(db)
    try:
        crud.log_admin_action(db, admin.id, "cleanup_orphans", result)
    except Exception:
        logger.exception("Audit log failed for cleanup_orphans")
    return RedirectResponse(url=f"/admin/settings?message={msg}", status_code=303)


@router.post("/maintenance/reset-application-data")
def maintenance_reset_application_data(
    request: Request,
    confirm_text: str = Form(...),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Reset all model and payout related data while retaining user accounts (admin only).

    Requires a secondary confirmation text 'RESET' to proceed.
    """
    if (confirm_text or "").strip().upper() != "RESET":
        return RedirectResponse(url="/admin/settings?error=Please+type+RESET+to+confirm", status_code=303)

    result = crud.reset_application_data(db)
    try:
        crud.log_admin_action(db, admin.id, "reset_application_data", result)
    except Exception:
        logger.exception("Audit log failed for reset_application_data")
    msg = (
        f"Reset complete: models={result.get('models',0)}, runs={result.get('schedule_runs',0)}, "
        f"payouts={result.get('payouts',0)}, validations={result.get('validations',0)}, "
        f"adhoc={result.get('adhoc_payments',0)}, adjustments={result.get('adjustments',0)}, "
        f"advances={result.get('model_advances',0)}, repayments={result.get('advance_repayments',0)}."
    )
    return RedirectResponse(url=f"/admin/settings?message={msg}", status_code=303)


# --- JSON API variants ------------------------------------------------------

@router.get("/diagnostics/db")
def diagnostics_db(
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Return a sanitized snapshot of the current database backend (admin only).

    This reveals only high-level details needed for SRE checks and avoids leaking
    credentials. Use it to confirm whether production is connected to Postgres
    or SQLite.
    """
    # Determine dialect in use by the live engine
    dialect = engine.dialect.name  # e.g., 'postgresql' or 'sqlite'
    driver = getattr(engine.dialect, "driver", None)

    # Parse configured DATABASE_URL safely (masking any password)
    try:
        parsed = make_url(DATABASE_URL)
        scheme = parsed.drivername
    except Exception:
        logger.exception("Failed to parse DATABASE_URL")
        scheme = None

    is_sqlite = dialect == "sqlite"
    is_postgres = dialect in ("postgresql", "postgres")

    # Base payload — never expose connection details regardless of environment
    payload = {
        "dialect": dialect,
        "driver": driver,
        "url_scheme": scheme,
        "is_sqlite": is_sqlite,
        "is_postgres": is_postgres,
    }

    return JSONResponse(payload)

@router.get("/api/models/{model_id}/purge")
def api_purge_model_preview(
    model_id: int,
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    impact = crud.get_model_purge_impact(db, model_id)
    return JSONResponse({"dry_run": True, "impact": impact})


@router.post("/api/models/{model_id}/purge")
def api_purge_model_execute(
    model_id: int,
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if dry_run:
        impact = crud.get_model_purge_impact(db, model_id)
        return JSONResponse({"dry_run": True, "impact": impact})
    impact = crud.purge_model_hard(db, model_id)
    try:
        crud.log_admin_action(db, admin.id, "purge_model", {"impact": impact, "api": True})
    except Exception:
        logger.exception("Audit log failed for purge_model (API)")
    return JSONResponse({"dry_run": False, "impact": impact})


# --- Audit log viewer -------------------------------------------------------

@router.get("/audit-log")
def audit_log_viewer(
    request: Request,
    page: int = Query(default=1, ge=1),
    action: str | None = Query(default=None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """List audit log entries (admin only)."""
    per_page = 50
    offset = (page - 1) * per_page
    logs, total = crud.list_audit_logs(db, limit=per_page, offset=offset, action_filter=action or None)

    # Batch-load usernames for display
    user_ids = {log.user_id for log in logs if log.user_id}
    users_by_id: dict[int, User] = {}
    if user_ids:
        users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "admin/audit_log.html",
        {
            "request": request,
            "user": admin,
            "logs": logs,
            "users_by_id": users_by_id,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "action_filter": action or "",
        },
    )


@router.get("/advances/pending")
def pending_advances_page(
    request: Request,
    message: str | None = Query(default=None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """List all advances awaiting approval with bulk-approve option."""
    pending = crud.list_pending_advances(db)
    advance_data = []
    for adv in pending:
        model = crud.get_model(db, adv.model_id)
        advance_data.append({"advance": adv, "model": model})

    return templates.TemplateResponse(
        request,
        "admin/pending_advances.html",
        {
            "request": request,
            "user": admin,
            "advances": advance_data,
            "message": message,
        },
    )


@router.post("/advances/bulk-approve")
def bulk_approve_advances(
    request: Request,
    advance_ids: str = Form(""),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Bulk approve and activate selected advances."""
    if not advance_ids.strip():
        return RedirectResponse(url="/admin/advances/pending?message=No+advances+selected", status_code=303)

    try:
        ids = [int(aid.strip()) for aid in advance_ids.split(",") if aid.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid advance IDs")

    approved = 0
    for aid in ids:
        adv = crud.get_advance(db, aid)
        if adv and adv.status == "requested":
            crud.approve_advance(db, adv, activate=True)
            approved += 1

    try:
        crud.log_admin_action(db, admin.id, "bulk_approve_advances", {"count": approved, "ids": ids})
    except Exception:
        logger.exception("Audit log failed for bulk_approve_advances")

    return RedirectResponse(url=f"/admin/advances/pending?message={approved}+advances+approved", status_code=303)
