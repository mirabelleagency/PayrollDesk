"""Session and environment configuration helpers."""
from __future__ import annotations

import os

_MIN_SESSION_SECRET_LEN = 32


_DEV_ENVS = frozenset({"development", "dev", "local", "test"})


def current_environment() -> str:
    return os.getenv("ENVIRONMENT", "production").lower()


def is_development_environment() -> bool:
    return current_environment() in _DEV_ENVS


def is_test_environment() -> bool:
    return current_environment() == "test"


def get_session_secret() -> str:
    """Return the session signing secret.

    Only explicitly named development/test environments may use the documented
    fallback. Staging, production, and any unknown value fail closed.
    """
    secret = os.getenv("SESSION_SECRET", "").strip()
    if is_development_environment():
        if secret:
            return secret
        return "payrolldesk-dev-session-secret-change-me"

    if not secret:
        raise RuntimeError(
            f"SESSION_SECRET must be set when ENVIRONMENT={current_environment()!r}. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if len(secret) < _MIN_SESSION_SECRET_LEN:
        raise RuntimeError(
            f"SESSION_SECRET must be at least {_MIN_SESSION_SECRET_LEN} characters "
            f"when ENVIRONMENT={current_environment()!r}."
        )
    return secret


def session_cookie_secure() -> bool:
    """Use secure cookies outside development/test (HTTPS-only environments)."""
    return not is_development_environment()
