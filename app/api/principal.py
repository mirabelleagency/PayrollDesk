"""Immutable API principal returned from authentication."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiPrincipal:
    key_id: int
    scopes: tuple[str, ...]

    def grants(self, required: str) -> bool:
        from app.api.scopes import scopes_grant

        return scopes_grant(list(self.scopes), required)
