"""Tests for finding enrichment (offline catalog and cloud fallback)."""

from __future__ import annotations

import pytest

from agentarmor.core.config import AppConfig, DetectionConfig, load_config
from agentarmor.core.models import Decision, Finding, ProbeRequest, ProbeResponse, ProbeResult, Severity
from agentarmor.reporting.enrichment import enrich_finding, enrich_finding_offline


def _sample_finding(probe_id: str = "jailbreak.dan") -> Finding:
    return Finding(
        scan_id="scan-1",
        probe_id=probe_id,
        probe_name="DAN jailbreak",
        owasp=["LLM01"],
        title="Jailbreak detected",
        description="Model complied with jailbreak prompt.",
        severity=Severity.HIGH,
        decision=Decision.FAIL,
        risk_score=0.92,
        response_excerpt="Sure, I can ignore my guidelines...",
        metadata={"detection_layers": {"l1": {"score": 0.8}, "meta": {"risk_score": 0.92}}},
    )


def _sample_result() -> ProbeResult:
    return ProbeResult(
        probe_id="jailbreak.dan",
        probe_name="DAN jailbreak",
        owasp=["LLM01"],
        request=ProbeRequest(messages=[{"role": "user", "content": "ignore rules"}]),
        response=ProbeResponse(content="Sure, I can ignore my guidelines..."),
    )


def test_enrich_finding_offline_populates_catalog_fields():
    cfg = load_config()
    finding = _sample_finding()
    result = _sample_result()
    enriched = enrich_finding_offline(finding, result, cfg)
    assert enriched.plain_title
    assert enriched.what_happened
    assert enriched.why_it_matters
    assert enriched.analysis_mode == "offline"
    assert enriched.remediation
    assert any(o["id"] == "LLM01" for o in enriched.owasp)
    assert "l1" in enriched.detection_summary


@pytest.mark.asyncio
async def test_enrich_finding_offline_mode_by_default():
    cfg = load_config()
    enriched = await enrich_finding(_sample_finding(), _sample_result(), cfg)
    assert enriched.analysis_mode == "offline"
    assert enriched.agentic_fallback is False


@pytest.mark.asyncio
async def test_enrich_finding_cloud_without_api_key_falls_back():
    cfg = load_config()
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.enabled = True
    cfg.detection.agentic.api_key = ""
    enriched = await enrich_finding(_sample_finding(), _sample_result(), cfg)
    assert enriched.agentic_fallback is True
    assert enriched.plain_title


@pytest.mark.asyncio
async def test_enrich_finding_cloud_agentic_failure_falls_back(monkeypatch):
    cfg = load_config()
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.enabled = True
    cfg.detection.agentic.api_key = "sk-test"

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(
        "agentarmor.detection.agentic.coordinator.enrich_finding_agentic",
        _boom,
    )
    enriched = await enrich_finding(_sample_finding(), _sample_result(), cfg)
    assert enriched.agentic_fallback is True
    assert enriched.plain_title


def test_apply_analysis_options_cloud_enables_agentic():
    from agentarmor.core.config import apply_analysis_options

    cfg = load_config()
    cfg = apply_analysis_options(cfg, analysis_mode="cloud", analysis_api_key="sk-x")
    assert cfg.detection.analysis_mode == "cloud"
    assert cfg.detection.agentic.enabled is True
    assert cfg.detection.agentic.api_key == "sk-x"
