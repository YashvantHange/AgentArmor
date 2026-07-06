"""Scan API multi-agent red team validation."""

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app

client = TestClient(app)


def test_scan_requires_analysis_key(monkeypatch):
    """Every scan now requires a multi-agent analysis API key (offline mode removed)."""
    monkeypatch.delenv("AGENTARMOR_ANALYSIS_API_KEY", raising=False)
    r = client.post(
        "/v1/scans",
        json={
            "target_type": "endpoint",
            "url": "http://127.0.0.1:8000/v1/chat",
            "scan_mode": "multi_agent_redteam",
        },
    )
    assert r.status_code == 400
    assert "analysis API key" in r.json()["detail"]
