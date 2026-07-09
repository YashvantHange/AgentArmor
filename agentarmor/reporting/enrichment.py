"""Finding enrichment — local catalog pre-fill plus the cloud multi-agent pipeline.

Every scan runs the cloud multi-agent analysis. The catalog pre-fill below seeds
each finding with baseline wording and only surfaces on its own if the cloud
enrichment cannot complete (network/model error), in which case the finding is
flagged with ``agentic_fallback = True``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Finding, ProbeResult
from agentarmor.knowledge.issue_catalog import format_entry
from agentarmor.knowledge.owasp_llm import owasp_entries


class EnrichmentResult(BaseModel):
    plain_title: str = ""
    what_happened: str = ""
    why_it_matters: str = ""
    owasp: list[dict[str, str]] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    detection_summary: dict[str, str] = Field(default_factory=dict)
    agentic_notes: str | None = None
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    analysis_mode: str = "cloud"
    agentic_fallback: bool = False


def enrich_finding_base(
    finding: Finding,
    result: ProbeResult,
    config: AppConfig,
) -> EnrichmentResult:
    """Seed a finding with catalog-based wording before cloud enrichment runs."""
    target_type = config.target.type.value
    formatted = format_entry(
        finding.probe_id,
        target_type=target_type,
        probe_name=finding.probe_name,
        response_excerpt=finding.response_excerpt,
    )
    layers = finding.metadata.get("detection_layers", {})
    return EnrichmentResult(
        plain_title=formatted["plain_title"],
        what_happened=formatted["what_happened"],
        why_it_matters=formatted["why_it_matters"],
        owasp=owasp_entries(finding.owasp),
        remediation=formatted["remediation"],
        detection_summary=_summarize_layers(layers),
        analysis_mode="cloud",
    )


async def enrich_finding(
    finding: Finding,
    result: ProbeResult,
    config: AppConfig,
) -> EnrichmentResult:
    base = enrich_finding_base(finding, result, config)

    api_key = config.detection.agentic.api_key or ""
    if not api_key:
        base.agentic_fallback = True
        return base

    try:
        from agentarmor.detection.agentic.coordinator import enrich_finding_agentic

        cloud = await enrich_finding_agentic(finding, result, config, base_enrichment=base)
        return cloud
    except Exception:
        base.agentic_fallback = True
        return base


def _summarize_layers(layers: dict[str, Any]) -> dict[str, str]:
    summary: dict[str, str] = {}
    if not isinstance(layers, dict):
        return summary
    l1 = layers.get("l1", {})
    if isinstance(l1, dict) and l1.get("score") is not None:
        summary["l1"] = f"Signature score {float(l1.get('score', 0)):.2f}"
    l2 = layers.get("l2", {})
    if isinstance(l2, dict) and l2.get("max_score") is not None:
        summary["l2"] = f"Classifier {l2.get('top_class', 'n/a')} ({float(l2.get('max_score', 0)):.2f})"
    l3 = layers.get("l3", {})
    if isinstance(l3, dict) and l3.get("score") is not None:
        summary["l3"] = f"Semantic similarity {float(l3.get('score', 0)):.2f}"
    l4 = layers.get("l4", {})
    if isinstance(l4, dict) and l4.get("score") is not None:
        summary["l4"] = f"Structural score {float(l4.get('score', 0)):.2f}"
    meta = layers.get("meta", {})
    if isinstance(meta, dict) and meta.get("risk_score") is not None:
        summary["meta"] = f"Combined risk {float(meta.get('risk_score', 0)):.2f}"
    return summary
