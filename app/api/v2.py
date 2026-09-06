"""Read-only external API v2 routes with snapshot revision consistency."""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import crud
from app.api.deps import api_read_db, require_any_v2_scope, require_scope
from app.api.principal import ApiPrincipal
from app.api.scopes import V2_RESOURCES
from app.api.v2_helpers import paginate_v2_collection
from app.api.v2_schemas import (
    ModelsQuery,
    PayoutsQuery,
    V2Adjustment,
    V2Advance,
    V2AdvanceAllocation,
    V2AdvanceRepayment,
    V2AdhocPayment,
    V2Detail,
    V2Model,
    V2Page,
    V2Payout,
    V2ScheduleRun,
    V2SnapshotResponse,
    V2ValidationIssue,
)
from app.api.v2_serializers import (
    serialize_v2_adhoc,
    serialize_v2_adjustment,
    serialize_v2_advance,
    serialize_v2_allocation,
    serialize_v2_model,
    serialize_v2_payout,
    serialize_v2_repayment,
    serialize_v2_schedule_run,
    serialize_v2_validation_issue,
)
from app.sync import get_sync_revision

router = APIRouter()


def _v2_enabled() -> bool:
    return os.getenv("API_V2_ENABLED", "true").lower() in ("1", "true", "yes")


def _ensure_v2_enabled() -> None:
    if not _v2_enabled():
        raise HTTPException(status_code=404, detail="API v2 is not enabled")


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field}; use YYYY-MM-DD.") from exc


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be on or after date_from.")


class ScheduleRunsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class ValidationIssuesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int | None = Field(default=None, ge=1)
    model_id: int | None = Field(default=None, ge=1)
    severity: str | None = None
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AdhocQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    model_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AdjustmentsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: str | None = None
    date_to: str | None = None
    model_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AdvancesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    model_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class RepaymentsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    advance_id: int | None = Field(default=None, ge=1)
    payout_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AllocationsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int | None = Field(default=None, ge=1)
    payout_id: int | None = Field(default=None, ge=1)
    model_id: int | None = Field(default=None, ge=1)
    advance_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


def _authorized_collections(principal: ApiPrincipal) -> list[str]:
    return [resource for resource in V2_RESOURCES if principal.grants(f"v2:{resource}")]


def _detail_response(db: Session, *, snapshot_revision: int, payload: dict[str, Any]) -> V2Detail:
    pre = get_sync_revision(db)
    if pre != snapshot_revision:
        raise HTTPException(
            status_code=409,
            detail={"code": "snapshot_changed", "message": "Domain revision changed"},
        )
    post = get_sync_revision(db)
    if pre != post:
        raise HTTPException(
            status_code=409,
            detail={"code": "snapshot_changed", "message": "Domain revision changed"},
        )
    return V2Detail(data=payload, snapshot_revision=pre)


@router.get("/snapshot", response_model=V2SnapshotResponse)
def snapshot(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_any_v2_scope),
):
    _ensure_v2_enabled()
    collections = _authorized_collections(principal)
    if not collections:
        raise HTTPException(status_code=403, detail="No v2 collections authorized for this key")
    return V2SnapshotResponse(revision=get_sync_revision(db), collections=collections)


@router.get("/models", response_model=V2Page[V2Model])
def list_models_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:models")),
    query: ModelsQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="models",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_models_api(
            db,
            code=query.code,
            status=query.status.value if query.status else None,
            payment_frequency=query.payment_frequency.value if query.payment_frequency else None,
            payment_method=query.payment_method,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_model,
    )


@router.get("/models/{model_id}", response_model=V2Detail[V2Model])
def get_model_v2(
    model_id: int,
    snapshot_revision: int = Query(..., ge=0),
    db: Session = Depends(api_read_db),
    _: ApiPrincipal = Depends(require_scope("v2:models")),
):
    _ensure_v2_enabled()
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return _detail_response(db, snapshot_revision=snapshot_revision, payload=serialize_v2_model(model))


@router.get("/payouts", response_model=V2Page[V2Payout])
def list_payouts_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:payouts")),
    query: PayoutsQuery = Depends(),
):
    _ensure_v2_enabled()
    start = _parse_date(query.date_from, "date_from")
    end = _parse_date(query.date_to, "date_to")
    _validate_date_range(start, end)
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="payouts",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_payouts_api(
            db,
            date_from=start,
            date_to=end,
            status=query.status.value if query.status else None,
            model_id=query.model_id,
            run_id=query.run_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_payout,
    )


@router.get("/schedule-runs", response_model=V2Page[V2ScheduleRun])
def list_schedule_runs_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:schedule-runs")),
    query: ScheduleRunsQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="schedule-runs",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_schedule_runs_api(
            db, year=query.year, month=query.month, after_id=after_id, limit=query.limit + 1
        ),
        serialize=serialize_v2_schedule_run,
    )


@router.get("/schedule-runs/{run_id}", response_model=V2Detail[V2ScheduleRun])
def get_schedule_run_v2(
    run_id: int,
    snapshot_revision: int = Query(..., ge=0),
    db: Session = Depends(api_read_db),
    _: ApiPrincipal = Depends(require_scope("v2:schedule-runs")),
):
    _ensure_v2_enabled()
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")
    return _detail_response(db, snapshot_revision=snapshot_revision, payload=serialize_v2_schedule_run(run))


@router.get("/validation-issues", response_model=V2Page[V2ValidationIssue])
def list_validation_issues_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:validation-issues")),
    query: ValidationIssuesQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="validation-issues",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_validation_issues_api(
            db,
            run_id=query.run_id,
            model_id=query.model_id,
            severity=query.severity,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_validation_issue,
    )


@router.get("/adhoc-payments", response_model=V2Page[V2AdhocPayment])
def list_adhoc_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:adhoc-payments")),
    query: AdhocQuery = Depends(),
):
    _ensure_v2_enabled()
    start = _parse_date(query.date_from, "date_from")
    end = _parse_date(query.date_to, "date_to")
    _validate_date_range(start, end)
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="adhoc-payments",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_adhoc_payments_api(
            db,
            date_from=start,
            date_to=end,
            status=query.status,
            model_id=query.model_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_adhoc,
    )


@router.get("/adjustments", response_model=V2Page[V2Adjustment])
def list_adjustments_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:adjustments")),
    query: AdjustmentsQuery = Depends(),
):
    _ensure_v2_enabled()
    start = _parse_date(query.date_from, "date_from")
    end = _parse_date(query.date_to, "date_to")
    _validate_date_range(start, end)
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="adjustments",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_adjustments_api(
            db,
            date_from=start,
            date_to=end,
            model_id=query.model_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_adjustment,
    )


@router.get("/advances", response_model=V2Page[V2Advance])
def list_advances_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:advances")),
    query: AdvancesQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="advances",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_advances_api(
            db,
            status=query.status,
            model_id=query.model_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_advance,
    )


@router.get("/advances/{advance_id}", response_model=V2Detail[V2Advance])
def get_advance_v2(
    advance_id: int,
    snapshot_revision: int = Query(..., ge=0),
    db: Session = Depends(api_read_db),
    _: ApiPrincipal = Depends(require_scope("v2:advances")),
):
    _ensure_v2_enabled()
    advance = crud.get_advance(db, advance_id)
    if not advance:
        raise HTTPException(status_code=404, detail="Advance not found")
    return _detail_response(db, snapshot_revision=snapshot_revision, payload=serialize_v2_advance(advance))


@router.get("/advance-repayments", response_model=V2Page[V2AdvanceRepayment])
def list_repayments_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:advance-repayments")),
    query: RepaymentsQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="advance-repayments",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_advance_repayments_api(
            db,
            advance_id=query.advance_id,
            payout_id=query.payout_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_repayment,
    )


@router.get("/advance-allocations", response_model=V2Page[V2AdvanceAllocation])
def list_allocations_v2(
    db: Session = Depends(api_read_db),
    principal: ApiPrincipal = Depends(require_scope("v2:advance-allocations")),
    query: AllocationsQuery = Depends(),
):
    _ensure_v2_enabled()
    filters = query.model_dump(exclude={"cursor", "snapshot_revision", "limit"}, exclude_none=True)
    return paginate_v2_collection(
        db,
        resource="advance-allocations",
        filters=filters,
        limit=query.limit,
        snapshot_revision=query.snapshot_revision,
        cursor=query.cursor,
        key_id=principal.key_id,
        fetch_rows=lambda after_id: crud.list_advance_allocations_api(
            db,
            run_id=query.run_id,
            payout_id=query.payout_id,
            model_id=query.model_id,
            advance_id=query.advance_id,
            after_id=after_id,
            limit=query.limit + 1,
        ),
        serialize=serialize_v2_allocation,
    )
