"""HMAC-signed opaque cursors for API v2 pagination."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import HTTPException

from app.env_config import is_development_environment, is_test_environment

CURSOR_VERSION = 1
CURSOR_TTL_SECONDS = 3600


def _cursor_secret() -> str:
    secret = os.getenv("API_CURSOR_SECRET", "").strip()
    if secret:
        if len(secret) < 32 and not (is_development_environment() or is_test_environment()):
            raise RuntimeError("API_CURSOR_SECRET must be at least 32 characters outside dev/test.")
        return secret
    if is_development_environment() or is_test_environment():
        return "dev-cursor-secret-not-for-production-32"
    raise RuntimeError("API_CURSOR_SECRET is required outside development/test.")


def canonical_fingerprint(filters: dict[str, Any]) -> str:
    normalized = {k: filters[k] for k in sorted(filters.keys())}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sign_cursor(
    *,
    api_version: str,
    resource: str,
    fingerprint: str,
    snapshot_revision: int,
    last_id: int,
    key_id: int,
) -> str:
    issued_at = int(time.time())
    payload = {
        "v": CURSOR_VERSION,
        "api": api_version,
        "resource": resource,
        "fp": fingerprint,
        "rev": snapshot_revision,
        "last": last_id,
        "kid": key_id,
        "iat": issued_at,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(_cursor_secret().encode(), raw, hashlib.sha256).hexdigest()
    token = json.dumps({"p": payload, "s": sig}, separators=(",", ":"))
    return token


def verify_cursor(
    token: str,
    *,
    api_version: str,
    resource: str,
    fingerprint: str,
    key_id: int,
) -> tuple[int, int]:
    try:
        outer = json.loads(token)
        payload = outer["p"]
        sig = outer["s"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(_cursor_secret().encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid cursor signature")

    if payload.get("v") != CURSOR_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported cursor version")
    if payload.get("api") != api_version:
        raise HTTPException(status_code=400, detail="Cursor API version mismatch")
    if payload.get("resource") != resource:
        raise HTTPException(status_code=400, detail="Cursor resource mismatch")
    if payload.get("fp") != fingerprint:
        raise HTTPException(status_code=400, detail="Cursor filter mismatch")
    if payload.get("kid") != key_id:
        raise HTTPException(status_code=400, detail="Cursor key mismatch")

    issued_at = int(payload.get("iat", 0))
    if time.time() - issued_at > CURSOR_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="Cursor expired")

    return int(payload["rev"]), int(payload["last"])
