"""Tests for the post-scan cloud-analysis health annotation."""

from __future__ import annotations

from agentarmor.core.config import load_config
from agentarmor.core.models import Decision, Finding, Scan, Severity, Target
from agentarmor.services.scan_service import _annotate_analysis_health


def _finding(fallback: bool, error: str | None = None) -> Finding:
    trace = [{"agent": "triage", "error": error, "status": "error" if error else "ok"}]
    return Finding(
        scan_id="s1",
        probe_id="l1.dan",
        probe_name="DAN",
        owasp=["LLM01"],
        title="Jailbreak",
        severity=Severity.HIGH,
        decision=Decision.FAIL,
        risk_score=0.8,
        response_excerpt="ok",
        metadata={"enrichment": {"agentic_fallback": fallback, "agent_trace": trace}},
    )


def _scan() -> Scan:
    return Scan(target=Target(url="http://localhost/v1/chat/completions"))


def test_all_fallback_sets_cloud_not_ok():
    cfg = load_config()
    cfg.detection.agentic.enabled = True
    scan = _scan()
    _annotate_analysis_health(cfg, scan, [_finding(True), _finding(True, "AuthenticationError: bad key")])
    health = scan.metadata.get("analysis_health")
    assert health and health["cloud_ok"] is False
    assert "invalid key" in health["message"]


def test_some_cloud_ok_no_warning():
    cfg = load_config()
    cfg.detection.agentic.enabled = True
    scan = _scan()
    _annotate_analysis_health(cfg, scan, [_finding(True), _finding(False)])
    assert "analysis_health" not in scan.metadata


def test_no_findings_no_warning():
    cfg = load_config()
    cfg.detection.agentic.enabled = True
    scan = _scan()
    _annotate_analysis_health(cfg, scan, [])
    assert "analysis_health" not in scan.metadata
