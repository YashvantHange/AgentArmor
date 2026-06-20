"""Scan API tests for GUI integration."""

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_roundtrip():
    r = client.get("/v1/settings")
    assert r.status_code == 200
    r2 = client.put("/v1/settings", json={"l5_enabled": False, "portable_mode": True})
    assert r2.status_code == 200
    assert r2.json()["portable_mode"] is True


@pytest.mark.asyncio
async def test_create_agent_scan(monkeypatch, detection_config):
    import agentarmor.api.routes.scans as scans_routes

    monkeypatch.setattr(scans_routes, "_app_config", scans_routes._app_config.model_copy())
    scans_routes._app_config.detection = detection_config

    async def fake_execute(config, scan_id=None, **kwargs):
        from agentarmor.core.models import Scan, ScanStatus, Target, TargetType

        scan = Scan(
            id=scan_id or "test",
            target=Target(type=TargetType.AGENT, agent_framework="crewai"),
            status=ScanStatus.COMPLETED,
            probe_count=5,
            finding_count=3,
            metadata={"reports": ["/tmp/scan-test.html"]},
        )
        scans_routes._repo.save_scan(scan)
        return scan, []

    monkeypatch.setattr("agentarmor.api.routes.scans.execute_scan", fake_execute)

    r = client.post("/v1/scans", json={"target_type": "agent", "agent": "crewai"})
    assert r.status_code == 200
    scan_id = r.json()["scan_id"]

    import time

    time.sleep(0.2)
    r2 = client.get(f"/v1/scans/{scan_id}")
    assert r2.status_code == 200
    assert r2.json()["finding_count"] == 3

    r3 = client.get(f"/v1/scans/{scan_id}/reports")
    assert "/tmp/scan-test.html" in r3.json()["reports"]
