"""The model snapshot picker must not inject model names as HTML."""
from fastapi.testclient import TestClient

from app.main import app


def test_snapshot_picker_builds_options_with_text_content():
    client = TestClient(app)
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    assert resp.status_code in (303, 307)

    page = client.get("/models/snapshot")
    assert page.status_code == 200
    # Before: listItem.innerHTML = `<span ...>${option.code}</span>...${option.working_name}...`
    assert 'innerHTML = `<span class="combobox-option__code">' not in page.text
    assert "nameSpan.textContent = option.working_name" in page.text
