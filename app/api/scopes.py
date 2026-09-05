"""API scope constants and validation."""
from __future__ import annotations

V1_RESOURCES = (
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

V2_RESOURCES = V1_RESOURCES

ALL_KNOWN_SCOPES: set[str] = set()
for resource in V1_RESOURCES:
    ALL_KNOWN_SCOPES.add(f"v1:{resource}")
    ALL_KNOWN_SCOPES.add(f"v2:{resource}")
ALL_KNOWN_SCOPES.update({"v1:*", "v2:*"})


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
