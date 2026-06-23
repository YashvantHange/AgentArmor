"""Scan API multi-agent red team validation."""

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app

client = TestClient(app)


def test_multi_agent_redteam_requires_cloud_key():
    r = client.post(
        "/v1/scans",
        json={
            "target_type": "endpoint",
            "url": "http://127.0.0.1:8000/v1/chat",
            "scan_mode": "multi_agent_redteam",
            "analysis_mode": "offline",
        },
    )
    assert r.status_code == 400
    assert "multi_agent_redteam" in r.json()["detail"]
