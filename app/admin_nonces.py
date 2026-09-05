"""Admin form nonce storage and consumption."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AdminActionNonce
from app.time_utils import utc_now

NONCE_TTL_MINUTES = 15


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_admin_nonce(db: Session, *, user_id: int, purpose: str) -> str:
    token = secrets.token_urlsafe(32)
    nonce = AdminActionNonce(
        token_hash=_hash_token(token),
        user_id=user_id,
        purpose=purpose,
        expires_at=utc_now() + timedelta(minutes=NONCE_TTL_MINUTES),
    )
    db.add(nonce)
    db.flush()
    return token


def consume_admin_nonce(db: Session, *, user_id: int, purpose: str, token: str) -> None:
    if not token:
        raise HTTPException(status_code=400, detail="Missing form nonce")
    token_hash = _hash_token(token.strip())
    nonce = (
        db.query(AdminActionNonce)
        .filter(
            AdminActionNonce.token_hash == token_hash,
            AdminActionNonce.user_id == user_id,
            AdminActionNonce.purpose == purpose,
            AdminActionNonce.consumed_at.is_(None),
        )
        .first()
    )
    if nonce is None or nonce.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="Invalid or expired form nonce")
    nonce.consumed_at = utc_now()
    db.add(nonce)
    db.flush()
