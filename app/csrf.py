"""CSRF protection for admin form posts."""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Request


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf_token(request: Request, submitted: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
