"""Read-only external API v1 routes."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Sequence, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import __version__
from app import crud
from app.api.deps import require_any_v1_scope, require_scope, require_v1_advance_detail
from app.api.principal import ApiPrincipal
from app.api.schemas import ApiCatalogResponse, DetailResponse, PaginatedResponse, PaginationMeta
from app.api.serializers import (
    serialize_adhoc_payment,
    serialize_adjustment,
    serialize_advance,
    serialize_advance_allocation,
    serialize_advance_repayment,
    serialize_model,
    serialize_payout,
    serialize_schedule_run,
    serialize_validation_issue,
)
from app.database import get_session

router = APIRouter()

T = TypeVar("T")


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


def _paginate(limit: int, rows: Sequence[T]) -> tuple[list[T], PaginationMeta]:
    has_more = len(rows) > limit
    page = list(rows[:limit])
    next_cursor = page[-1].id if has_more and page else None  # type: ignore[attr-defined]
    return page, PaginationMeta(limit=limit, next_cursor=next_cursor, has_more=has_more)


def _collection_response(limit: int, rows: Sequence[T], serializer: Callable[[T], dict[str, Any]]) -> PaginatedResponse:
    page, pagination = _paginate(limit, rows)
    return PaginatedResponse(data=[serializer(row) for row in page], pagination=pagination)


@router.get("", response_model=ApiCatalogResponse)
def api_catalog(_: ApiPrincipal = Depends(require_any_v1_scope)):
    return ApiCatalogResponse(
        version=__version__,
        endpoints=[
            "GET /api/v1/models",
            "GET /api/v1/models/{id}",
            "GET /api/v1/payouts",
            "GET /api/v1/schedule-runs",
            "GET /api/v1/schedule-runs/{id}",
            "GET /api/v1/validation-issues",
            "GET /api/v1/adhoc-payments",
            "GET /api/v1/adjustments",
            "GET /api/v1/advances",
            "GET /api/v1/advances/{id}",
            "GET /api/v1/advance-repayments",
            "GET /api/v1/advance-allocations",
        ],
    )


@router.get("/models", response_model=PaginatedResponse)
def list_models(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:models")),
    code: str | None = None,
    status: str | None = None,
    payment_frequency: str | None = None,
    payment_method: str | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_models_api(
        db,
        code=code,
        status=status,
        payment_frequency=payment_frequency,
        payment_method=payment_method,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_model)


@router.get("/models/{model_id}", response_model=DetailResponse)
def get_model(
    model_id: int,
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:models")),
):
    model = crud.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return DetailResponse(data=serialize_model(model))


@router.get("/payouts", response_model=PaginatedResponse)
def list_payouts(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:payouts")),
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    model_id: int | None = None,
    run_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")
    _validate_date_range(start, end)
    rows = crud.list_payouts_api(
        db,
        date_from=start,
        date_to=end,
        status=status,
        model_id=model_id,
        run_id=run_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_payout)


@router.get("/schedule-runs", response_model=PaginatedResponse)
def list_schedule_runs(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:schedule-runs")),
    year: int | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_schedule_runs_api(db, year=year, month=month, after_id=after_id, limit=limit)
    return _collection_response(limit, rows, serialize_schedule_run)


@router.get("/schedule-runs/{run_id}", response_model=DetailResponse)
def get_schedule_run(
    run_id: int,
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:schedule-runs")),
):
    run = crud.get_schedule_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Schedule run not found")
    return DetailResponse(data=serialize_schedule_run(run))


@router.get("/validation-issues", response_model=PaginatedResponse)
def list_validation_issues(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:validation-issues")),
    run_id: int | None = None,
    model_id: int | None = None,
    severity: str | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_validation_issues_api(
        db,
        run_id=run_id,
        model_id=model_id,
        severity=severity,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_validation_issue)


@router.get("/adhoc-payments", response_model=PaginatedResponse)
def list_adhoc_payments(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:adhoc-payments")),
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    model_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")
    _validate_date_range(start, end)
    rows = crud.list_adhoc_payments_api(
        db,
        date_from=start,
        date_to=end,
        status=status,
        model_id=model_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_adhoc_payment)


@router.get("/adjustments", response_model=PaginatedResponse)
def list_adjustments(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:adjustments")),
    date_from: str | None = None,
    date_to: str | None = None,
    model_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")
    _validate_date_range(start, end)
    rows = crud.list_adjustments_api(
        db,
        date_from=start,
        date_to=end,
        model_id=model_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_adjustment)


@router.get("/advances", response_model=PaginatedResponse)
def list_advances(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:advances")),
    status: str | None = None,
    model_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_advances_api(
        db,
        status=status,
        model_id=model_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, lambda a: serialize_advance(a, include_repayments=False))


@router.get("/advances/{advance_id}", response_model=DetailResponse)
def get_advance(
    advance_id: int,
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_v1_advance_detail),
):
    advance = crud.get_advance_with_repayments(db, advance_id)
    if not advance:
        raise HTTPException(status_code=404, detail="Advance not found")
    return DetailResponse(data=serialize_advance(advance, include_repayments=True))


@router.get("/advance-repayments", response_model=PaginatedResponse)
def list_advance_repayments(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:advance-repayments")),
    advance_id: int | None = None,
    payout_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_advance_repayments_api(
        db,
        advance_id=advance_id,
        payout_id=payout_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_advance_repayment)


@router.get("/advance-allocations", response_model=PaginatedResponse)
def list_advance_allocations(
    db: Session = Depends(get_session),
    _: ApiPrincipal = Depends(require_scope("v1:advance-allocations")),
    run_id: int | None = None,
    payout_id: int | None = None,
    model_id: int | None = None,
    advance_id: int | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = crud.list_advance_allocations_api(
        db,
        run_id=run_id,
        payout_id=payout_id,
        model_id=model_id,
        advance_id=advance_id,
        after_id=after_id,
        limit=limit,
    )
    return _collection_response(limit, rows, serialize_advance_allocation)
