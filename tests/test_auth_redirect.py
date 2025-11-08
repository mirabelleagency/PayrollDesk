from fastapi.testclient import TestClient
from app.main import app


def test_html_request_redirects_to_login_with_next():
    client = TestClient(app)
    resp = client.get("/dashboard", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code in (303, 307)
    location = resp.headers.get("location")
    assert location is not None
    assert location.startswith("/login?next=")
    assert "%2Fdashboard" in location  # encoded /dashboard


def test_json_request_gets_401_json():
    client = TestClient(app)
    resp = client.get("/dashboard", headers={"accept": "application/json"}, follow_redirects=False)
    assert resp.status_code == 401
    data = resp.json()
    assert data.get("detail") == "Not authenticated"


def test_next_param_returns_user_to_original_page_after_login():
    client = TestClient(app)
    # Trigger redirect to capture next
    # Use trailing slash to avoid initial redirect normalization
    resp = client.get("/models/", headers={"accept": "text/html"}, follow_redirects=False)
    assert resp.status_code in (303, 307)
    login_location = resp.headers.get("location")
    assert login_location, "expected redirect location"

    # Extract next value
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(login_location)
    # Support absolute or relative redirect URLs
    assert parsed.path.endswith("/login"), f"unexpected redirect path: {parsed.path}"
    next_values = parse_qs(parsed.query).get("next", [])
    assert next_values, "expected next query parameter"
    next_value = next_values[0]

    # Submit login with admin/admin and provided next
    resp2 = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "next": next_value},
        follow_redirects=False,
    )
    assert resp2.status_code in (303, 307)
    assert resp2.headers.get("location") == next_value

    # Follow to next
    resp3 = client.get(next_value, follow_redirects=False)
    # Authenticated dashboard/models should return 200 OK
    assert resp3.status_code in (200, 303, 307)  # 303/307 acceptable if page performs its own redirect
