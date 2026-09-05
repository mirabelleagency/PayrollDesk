"""Pydantic response models for the external API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    limit: int
    next_cursor: int | None = None
    has_more: bool


class PaginatedResponse(BaseModel):
    data: list[Any]
    pagination: PaginationMeta


class DetailResponse(BaseModel):
    data: dict[str, Any]


class ApiCatalogResponse(BaseModel):
    version: str
    endpoints: list[str]
