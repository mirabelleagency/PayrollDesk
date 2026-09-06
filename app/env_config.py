"""Environment helpers for API secrets and fail-closed production defaults."""
from __future__ import annotations

import os

_MIN_SECRET_LEN = 32
_DEV_ENVS = frozenset({"development", "dev", "local", "test"})


def current_environment() -> str:
    return os.getenv("ENVIRONMENT", "production").lower()


def is_development_environment() -> bool:
    return current_environment() in _DEV_ENVS


def is_test_environment() -> bool:
    return current_environment() == "test"


def validate_api_secrets_at_startup() -> None:
    """Ensure API signing secrets exist outside dev/test."""
    if is_development_environment() or is_test_environment():
        return
    for name in ("API_RATE_SECRET", "API_CURSOR_SECRET"):
        secret = os.getenv(name, "").strip()
        if not secret or len(secret) < _MIN_SECRET_LEN:
            raise RuntimeError(
                f"{name} must be set and at least {_MIN_SECRET_LEN} characters "
                f"when ENVIRONMENT={current_environment()!r}."
            )
