"""UTC datetime helpers for consistent storage and API serialization."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (SQLite-compatible)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_datetime_z(value: datetime | None) -> str | None:
    """Serialize naive UTC datetime with trailing Z for v2 API."""
    if value is None:
        return None
    return value.isoformat() + "Z"
