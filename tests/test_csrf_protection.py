"""Tests for CSRF token protection."""
from starlette.testclient import TestClient

from app.main import app
from conftest import csrf_token_for


def _login(client: TestClient) -> None:
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)


class TestCSRFProtection:
    """Verify that CSRF tokens are required on POST endpoints."""

    def test_post_without_token_returns_403(self):
        client = TestClient(app)
        _login(client)
        # POST to an admin endpoint without a CSRF token
        resp = client.post("/admin/maintenance/cleanup-empty-runs")
        assert resp.status_code == 403

    def test_post_with_invalid_token_returns_403(self):
        client = TestClient(app)
        _login(client)
        resp = client.post(
            "/admin/maintenance/cleanup-empty-runs",
            data={"_csrf_token": "bad-token"},
        )
        assert resp.status_code == 403

    def test_post_with_valid_token_succeeds(self):
        client = TestClient(app)
        _login(client)
        token = csrf_token_for(client)
        resp = client.post(
            "/admin/maintenance/cleanup-empty-runs",
            data={"_csrf_token": token},
            follow_redirects=False,
        )
        # Should succeed (303 redirect to settings page)
        assert resp.status_code == 303

    def test_login_exempt_from_csrf(self):
        client = TestClient(app)
        # Login should work without CSRF token
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert resp.status_code in (303, 307)

    def test_csrf_meta_tag_in_html(self):
        client = TestClient(app)
        _login(client)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b'<meta name="csrf-token"' in resp.content
        # Token should not be empty for authenticated users
        assert b'content=""' not in resp.content

    def test_unauthenticated_post_skips_csrf(self):
        client = TestClient(app)
        # POST without login — CSRF check skipped; auth rejects with redirect
        resp = client.post("/admin/maintenance/cleanup-empty-runs", follow_redirects=False)
        # Should redirect to login (401/302/303), NOT 403 CSRF error
        assert resp.status_code in (302, 303, 307, 401)
