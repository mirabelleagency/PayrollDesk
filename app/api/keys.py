"""API key generation, hashing, and lifecycle."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.scopes import normalize_scopes
from app.models import ApiKey
from app.time_utils import utc_now

KEY_PREFIX = "pd_"
DISPLAY_PREFIX_LEN = 12
EXPECTED_KEY_LEN = len(KEY_PREFIX) + 43


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, display_prefix, hash)."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    return plaintext, plaintext[:DISPLAY_PREFIX_LEN], hash_api_key(plaintext)


def validate_raw_key_format(raw_key: str) -> bool:
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return False
    if len(raw_key) != EXPECTED_KEY_LEN:
        return False
    token_part = raw_key[len(KEY_PREFIX) :]
    return token_part.replace("-", "").replace("_", "").isalnum()


def create_api_key_record(
    db: Session,
    *,
    name: str,
    created_by: str | None,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    name = name.strip()
    if not name:
        raise ValueError("API key name is required")
    if len(name) > 100:
        raise ValueError("API key name must be 100 characters or fewer")

    normalized = normalize_scopes(scopes)
    plaintext, prefix, key_hash = generate_api_key()
    record = ApiKey(
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=json.dumps(normalized),
        created_by=created_by,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return record, plaintext


def get_active_api_key(db: Session, raw_key: str) -> ApiKey | None:
    if not validate_raw_key_format(raw_key):
        return None
    key_hash = hash_api_key(raw_key)
    record = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    if record is None:
        return None
    if record.expires_at and record.expires_at <= utc_now():
        return None
    return record


def touch_api_key_usage(db: Session, api_key: ApiKey, *, min_interval_seconds: int = 60) -> None:
    now = utc_now()
    if api_key.last_used_at is None or (now - api_key.last_used_at).total_seconds() >= min_interval_seconds:
        api_key.last_used_at = now
        db.add(api_key)
        db.commit()


def revoke_api_key(
    db: Session,
    key_id: int,
    *,
    revoked_by: str | None = None,
    revoke_reason: str | None = None,
) -> ApiKey | None:
    record = db.get(ApiKey, key_id)
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = utc_now()
        record.revoked_by = revoked_by
        record.revoke_reason = revoke_reason
        db.add(record)
        db.flush()
    return record


def revoke_all_api_keys(
    db: Session,
    *,
    revoked_by: str | None = None,
    revoke_reason: str | None = None,
) -> int:
    now = utc_now()
    rows = db.query(ApiKey).filter(ApiKey.revoked_at.is_(None)).all()
    for row in rows:
        row.revoked_at = now
        row.revoked_by = revoked_by
        row.revoke_reason = revoke_reason
        db.add(row)
    db.flush()
    return len(rows)


def list_api_keys(db: Session) -> list[ApiKey]:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


def count_active_api_keys(db: Session) -> int:
    now = utc_now()
    return (
        db.query(ApiKey)
        .filter(ApiKey.revoked_at.is_(None))
        .filter((ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now))
        .count()
    )
