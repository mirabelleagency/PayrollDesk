"""API scope constants and validation."""
from __future__ import annotations

V2_RESOURCES = (
    "models",
    "payouts",
    "schedule-runs",
    "validation-issues",
    "adhoc-payments",
    "adjustments",
    "advances",
    "advance-repayments",
    "advance-allocations",
)

# The v1 API was removed (2026-10); keys still holding v1 scopes match no route.
ALL_KNOWN_SCOPES: set[str] = {f"v2:{resource}" for resource in V2_RESOURCES} | {"v2:*"}


def normalize_scopes(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for scope in raw:
        value = scope.strip()
        if not value or value in seen:
            continue
        if value not in ALL_KNOWN_SCOPES:
            raise ValueError(f"Unknown scope: {value}")
        seen.add(value)
        normalized.append(value)
    if not normalized:
        raise ValueError("At least one scope is required")
    return normalized


def scopes_grant(scopes: list[str], required: str) -> bool:
    if required in scopes:
        return True
    version, _, resource = required.partition(":")
    if f"{version}:*" in scopes:
        return True
    return False
