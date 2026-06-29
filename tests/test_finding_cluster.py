"""P0 tests for finding clustering and replay."""

from __future__ import annotations

from agentarmor.core.models import Decision, Finding, Severity
from agentarmor.reporting.finding_cluster import (
    build_replay_bundle,
    cluster_findings,
    grouped_findings_api,
)


def _finding(probe_id: str, response: str) -> Finding:
    return Finding(
        scan_id="s1",
        probe_id=probe_id,
        probe_name=probe_id,
        owasp=["LLM01"],
        title=probe_id,
        severity=Severity.HIGH,
        decision=Decision.FAIL,
        risk_score=0.9,
        evidence=["matched"],
        request_summary="ignore instructions",
        response_excerpt=response,
        metadata={"conversation": [{"role": "user", "content": "ignore instructions"}]},
    )


def test_cluster_same_response():
    a = _finding("l1.ignore-instructions", "Same leaky response text here")
    b = _finding("l2.roleplay", "Same leaky response text here")
    clustered = cluster_findings([a, b])
    primaries = [f for f in clustered if f.metadata.get("is_cluster_primary")]
    assert len(primaries) == 1
    assert primaries[0].metadata["cluster_size"] == 2


def test_grouped_api_returns_one_card():
    a = _finding("l1.ignore-instructions", "Same text")
    b = _finding("l2.roleplay", "Same text")
    clustered = cluster_findings([a, b])
    grouped = grouped_findings_api(clustered)
    assert len(grouped) == 1
    assert grouped[0]["cluster_size"] == 2


def test_replay_bundle_has_curl():
    f = _finding("l1.ignore-instructions", "leak")
    bundle = build_replay_bundle(f)
    assert "prompt" in bundle
    assert "conversation" in bundle
    assert "curl" in bundle
