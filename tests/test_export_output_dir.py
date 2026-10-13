"""A new schedule's files can only be written inside the exports folder."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers.schedules import DEFAULT_EXPORT_DIR, _export_dir


@pytest.mark.parametrize("value", [None, "", "exports", "exports/2026-10", "./exports/sub"])
def test_paths_inside_exports_are_allowed(value):
    result = _export_dir(value)
    root = DEFAULT_EXPORT_DIR.resolve()
    assert result == root or root in result.parents


@pytest.mark.parametrize("value", ["app/static", "app/static/schedules", "exports/../app/static", "/tmp", "..", "exportsX"])
def test_paths_outside_exports_are_refused(value):
    with pytest.raises(HTTPException) as exc:
        _export_dir(value)
    assert exc.value.status_code == 400


def test_new_schedule_route_refuses_static(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from conftest import csrf_token_for

    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    token = csrf_token_for(client)
    resp = client.post(
        "/schedules/new",
        data={"month": "2026-10", "output_dir": "app/static", "_csrf_token": token},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert not list(Path("app/static").glob("pay_schedule_2026_10*"))
