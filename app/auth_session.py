"""Session version management for revocable admin sessions."""
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth import User


def bump_session_version(db: Session, user: User) -> None:
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(session_version=User.session_version + 1)
    )
    db.refresh(user)


def store_session_user(request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["session_version"] = user.session_version


def validate_session_user(request, user: User) -> bool:
    session_version = request.session.get("session_version")
    if session_version is None:
        return False
    try:
        return int(session_version) == int(user.session_version)
    except (TypeError, ValueError):
        return False
