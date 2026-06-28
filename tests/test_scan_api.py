"""Scan API tests for GUI integration."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from agentarmor.api.app import app
from agentarmor.core.models import Scan, ScanStatus, Target, TargetType

client = TestClient(app)


def _save_scan_with_reports(repo, scan_id: str, report_paths: list[str]) -> None:
    scan = Scan(
        id=scan_id,
        target=Target(type=TargetType.ENDPOINT, url="http://127.0.0.1:8010/v1/chat/completions"),
        status=ScanStatus.COMPLETED,
        probe_count=3,
        finding_count=1,
        metadata={"reports": report_paths},
    )
    repo.save_scan(scan)


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


def test_download_report_happy_path(tmp_path, monkeypatch):
    import agentarmor.api.routes.scans as scans_routes

    html_path = tmp_path / "scan-dl-test.html"
    html_path.write_text("<html><body>report</body></html>", encoding="utf-8")

    monkeypatch.setattr(scans_routes, "_app_config", scans_routes._app_config.model_copy())
    scans_routes._app_config.reporting.output_dir = str(tmp_path)
    scans_routes._repo.ensure_schema()
    _save_scan_with_reports(scans_routes._repo, "dl-test", [str(html_path)])

    r = client.get("/v1/scans/dl-test/reports/download?format=html")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert b"report" in r.content


def test_download_report_missing(tmp_path, monkeypatch):
    import agentarmor.api.routes.scans as scans_routes

    monkeypatch.setattr(scans_routes, "_app_config", scans_routes._app_config.model_copy())
    scans_routes._app_config.reporting.output_dir = str(tmp_path)
    scans_routes._repo.ensure_schema()
    _save_scan_with_reports(scans_routes._repo, "missing-dl", [])

    r = client.get("/v1/scans/missing-dl/reports/download?format=pdf")
    assert r.status_code == 404


def test_download_report_path_traversal(tmp_path, monkeypatch):
    import agentarmor.api.routes.scans as scans_routes

    outside = tmp_path.parent / "outside-secret.html"
    outside.write_text("secret", encoding="utf-8")

    monkeypatch.setattr(scans_routes, "_app_config", scans_routes._app_config.model_copy())
    scans_routes._app_config.reporting.output_dir = str(tmp_path)
    scans_routes._repo.ensure_schema()
    _save_scan_with_reports(scans_routes._repo, "traversal-test", [str(outside)])

    r = client.get("/v1/scans/traversal-test/reports/download?format=html")
    assert r.status_code == 403


def test_download_report_zip(tmp_path, monkeypatch):
    import agentarmor.api.routes.scans as scans_routes

    html_path = tmp_path / "scan-zip-test.html"
    json_path = tmp_path / "scan-zip-test.json"
    html_path.write_text("<html></html>", encoding="utf-8")
    json_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(scans_routes, "_app_config", scans_routes._app_config.model_copy())
    scans_routes._app_config.reporting.output_dir = str(tmp_path)
    scans_routes._repo.ensure_schema()
    _save_scan_with_reports(scans_routes._repo, "zip-test", [str(html_path), str(json_path)])

    r = client.get("/v1/scans/zip-test/reports/download?format=zip")
    assert r.status_code == 200
    assert "application/zip" in r.headers.get("content-type", "")
    assert len(r.content) > 0
