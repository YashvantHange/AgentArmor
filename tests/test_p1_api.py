"""P1 API verification tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app
from agentarmor.core.models import Decision, Finding, Scan, ScanStatus, Severity, Target, TargetType
from agentarmor.db.session import ScanRepository

client = TestClient(app)


def test_list_scan_profiles():
    r = client.get("/v1/scans/profiles")
    assert r.status_code == 200
    profiles = r.json()
    assert len(profiles) >= 8
    ids = {p["id"] for p in profiles}
    assert "owasp_audit" in ids
    assert "full_red_team" in ids


def test_plan_preview_endpoint():
    r = client.post(
        "/v1/scans/plan-preview",
        json={
            "target_type": "endpoint",
            "url": "http://127.0.0.1:8010/v1/chat/completions",
            "scan_profile": "production_readiness",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["estimated_probes"] > 0
    assert "over_budget" in data
    assert "probes_by_owasp" in data


def test_scan_metrics_404():
    r = client.get("/v1/scans/nonexistent-id/metrics")
    assert r.status_code == 404


def test_scan_findings_grouped_endpoint(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'findings.db'}"
    repo = ScanRepository(db_url)
    repo.ensure_schema()

    from agentarmor.core.models import Decision, Finding, Scan, ScanStatus, Severity, Target, TargetType

    scan = Scan(
        id="scan-f1",
        target=Target(type=TargetType.ENDPOINT, url="http://x"),
        status=ScanStatus.COMPLETED,
    )
    repo.save_scan(scan)
    repo.save_finding(
        Finding(
            scan_id="scan-f1",
            probe_id="l1.test",
            probe_name="test",
            owasp=["LLM01"],
            title="Test",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.9,
            metadata={"is_cluster_primary": True, "cluster_size": 1},
        )
    )

    import agentarmor.api.routes.scans as scans_routes

    monkeypatch.setattr(scans_routes, "_repo", repo)

    r = client.get("/v1/scans/scan-f1/findings?grouped=true")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["probe_id"] == "l1.test"


def test_create_scan_rejects_over_budget(monkeypatch):
    import agentarmor.api.routes.scans as scans_routes

    async def _over_budget_preview(_cfg):
        return {
            "over_budget": True,
            "estimated_tokens": 999_999,
            "estimated_cost_usd": 99.0,
            "budget_limits": {"max_tokens": 100, "max_cost_usd": 1.0},
        }

    monkeypatch.setattr(scans_routes, "preview_scan_plan", _over_budget_preview)

    r = client.post(
        "/v1/scans",
        json={
            "target_type": "endpoint",
            "url": "http://127.0.0.1:8010/v1/chat/completions",
            "planner_v2": True,
            "scan_depth": "standard",
        },
    )
    assert r.status_code == 400
    assert "budget" in r.json()["detail"].lower()


def test_compare_scans_api(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'cmp.db'}"
    repo = ScanRepository(db_url)
    repo.ensure_schema()

    base_scan = Scan(
        id="base-1",
        target=Target(type=TargetType.ENDPOINT, url="http://x"),
        status=ScanStatus.COMPLETED,
    )
    curr_scan = Scan(
        id="curr-1",
        target=Target(type=TargetType.ENDPOINT, url="http://x"),
        status=ScanStatus.COMPLETED,
    )
    repo.save_scan(base_scan)
    repo.save_scan(curr_scan)

    repo.save_finding(
        Finding(
            scan_id="base-1",
            probe_id="l1.ignore-instructions",
            probe_name="ignore",
            owasp=["LLM01"],
            title="Injection",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.9,
            metadata={"root_cause": "prompt_injection", "is_cluster_primary": True},
        )
    )
    repo.save_finding(
        Finding(
            scan_id="curr-1",
            probe_id="l2.roleplay",
            probe_name="roleplay",
            owasp=["LLM01"],
            title="Injection",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.9,
            metadata={"root_cause": "prompt_injection", "is_cluster_primary": True},
        )
    )

    import agentarmor.api.routes.scans as scans_routes

    monkeypatch.setattr(scans_routes, "_repo", repo)

    r = client.post("/v1/scans/curr-1/compare/base-1")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["still_vulnerable_count"] == 1
