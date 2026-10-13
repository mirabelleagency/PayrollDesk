"""Login redirects stay on this site; no session secret outside dev/test fails closed."""
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import safe_redirect_path


@pytest.mark.parametrize(
    "target",
    [
        "//evil.com",
        "//evil.com/path",
        "/\evil.com",
        "https://evil.com",
        "http:/evil.com",
        "javascript:alert(1)",
        "evil.com",
        "",
        None,
        "/ok\nLocation: //evil.com",
    ],
)
def test_off_site_targets_fall_back(target):
    assert safe_redirect_path(target, "/dashboard") == "/dashboard"


@pytest.mark.parametrize("target", ["/dashboard", "/schedules/5?tab=payouts", "/models/3#advances"])
def test_on_site_paths_pass(target):
    assert safe_redirect_path(target, "/dashboard") == target


@pytest.mark.parametrize("next_param, expected", [("//evil.com", "/dashboard"), ("/schedules", "/schedules")])
def test_login_next(next_param, expected):
    client = TestClient(app)
    resp = client.post(
        f"/login?next={next_param}",
        data={"username": "admin", "password": "admin", "next": next_param},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == expected


def _import_auth(env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("SESSION_SECRET", "SECRET_KEY", "ENVIRONMENT")}
    env.update({k: v for k, v in env_overrides.items() if v is not None})
    return subprocess.run(
        [sys.executable, "-c", "import app.routers.auth"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def test_missing_secret_without_environment_refuses_to_start():
    # Before: a missing ENVIRONMENT counted as development, so this started
    # and signed sessions with the public default secret.
    result = _import_auth({})
    assert result.returncode != 0
    assert "SESSION_SECRET" in result.stderr


def test_placeholder_secret_in_production_refuses_to_start():
    result = _import_auth({"ENVIRONMENT": "production", "SESSION_SECRET": "change-me-in-production"})
    assert result.returncode != 0


def test_real_secret_in_production_starts():
    result = _import_auth({"ENVIRONMENT": "production", "SESSION_SECRET": "x" * 64})
    assert result.returncode == 0, result.stderr


def test_dev_without_secret_starts():
    result = _import_auth({"ENVIRONMENT": "development"})
    assert result.returncode == 0, result.stderr
