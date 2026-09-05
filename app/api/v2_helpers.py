"""Shared pagination helpers for API v2."""
from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.cursors import canonical_fingerprint, sign_cursor, verify_cursor
from app.api.v2_schemas import V2Page, V2Pagination
from app.sync import get_sync_revision

T = TypeVar("T")


def _snapshot_conflict() -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "snapshot_changed", "message": "Domain revision changed"})


def paginate_v2_collection(
    db: Session,
    *,
    resource: str,
    filters: dict[str, Any],
    limit: int,
    snapshot_revision: int | None,
    cursor: str | None,
    key_id: int,
    fetch_rows: Callable[[int | None], Sequence[T]],
    serialize: Callable[[T], dict[str, Any]],
) -> V2Page:
    fingerprint = canonical_fingerprint({**filters, "limit": limit})
    after_id: int | None = None
    expected_revision: int

    if cursor:
        expected_revision, after_id = verify_cursor(
            cursor,
            api_version="2",
            resource=resource,
            fingerprint=fingerprint,
            key_id=key_id,
        )
    elif snapshot_revision is None:
        raise HTTPException(status_code=400, detail="snapshot_revision is required for the first page")
    else:
        expected_revision = snapshot_revision

    pre_revision = get_sync_revision(db)
    if cursor:
        if pre_revision != expected_revision:
            raise _snapshot_conflict()
    elif pre_revision != expected_revision:
        raise _snapshot_conflict()

    rows = list(fetch_rows(after_id))
    has_more = len(rows) > limit
    page_rows = rows[:limit]

    post_revision = get_sync_revision(db)
    if pre_revision != post_revision or pre_revision != expected_revision:
        raise _snapshot_conflict()

    next_cursor = None
    if has_more and page_rows:
        last_id = getattr(page_rows[-1], "id")
        next_cursor = sign_cursor(
            api_version="2",
            resource=resource,
            fingerprint=fingerprint,
            snapshot_revision=pre_revision,
            last_id=int(last_id),
            key_id=key_id,
        )

    return V2Page(
        data=[serialize(row) for row in page_rows],
        pagination=V2Pagination(limit=limit, next_cursor=next_cursor, has_more=has_more),
        snapshot_revision=pre_revision,
    )
