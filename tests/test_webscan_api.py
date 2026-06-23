"""Web scan API smoke tests."""

from fastapi.testclient import TestClient

from agentarmor.api.app import app

client = TestClient(app)


def test_health_includes_webscan_ready():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "webscan_ready" in data


def test_webscan_capabilities():
    r = client.get("/v1/web-scans/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "webscan_ready" in data
    assert "standard" in data["scan_depths"]


def test_discover_rejects_localhost():
    r = client.post("/v1/web-scans/discover", json={"page_url": "http://127.0.0.1/"})
    # Without playwright: 503; with playwright: 200 with ok=false
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json()["ok"] is False


def test_create_rejects_manual_session_without_prepare():
    r = client.post(
        "/v1/web-scans",
        json={"page_url": "https://example.com", "auth_mode": "manual_session"},
    )
    if r.status_code == 503:
        return  # playwright missing
    assert r.status_code == 400
    assert "prepare-session" in r.json()["detail"]


def test_create_rejects_multi_agentic_without_key():
    r = client.post(
        "/v1/web-scans",
        json={"page_url": "https://example.com", "scan_depth": "multi_agentic", "analysis_mode": "cloud"},
    )
    if r.status_code == 503:
        return
    assert r.status_code == 400


def test_capabilities_includes_auth_modes():
    r = client.get("/v1/web-scans/capabilities")
    assert r.status_code == 200
    data = r.json()
    assert "manual_session" in data.get("auth_modes", [])
