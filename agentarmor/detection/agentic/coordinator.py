"""Multi-agent coordinator for cloud-enhanced finding enrichment."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Finding, ProbeResult
from agentarmor.detection.agentic.guardrails import (
    evidence_in_response,
    parse_json_model,
    truncate,
    validate_agentic_output,
)
from agentarmor.detection.agentic.prompts import (
    ANALYST_SYSTEM,
    OWASP_SYSTEM,
    REMEDIATION_SYSTEM,
    SYNTHESIS_SYSTEM,
    TRIAGE_SYSTEM,
)
from agentarmor.detection.agentic.schemas import (
    AnalystResult,
    OwaspMappingResult,
    RemediationResult,
    SynthesisResult,
    TriageResult,
)
from agentarmor.knowledge.owasp_llm import owasp_entries
from agentarmor.reporting.enrichment import EnrichmentResult


async def _llm_json(
    config: AppConfig,
    system: str,
    user: str,
    agent_name: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    import litellm

    agentic = config.detection.agentic
    timeout = max(5.0, agentic.timeout_s)
    start = time.perf_counter()
    trace: dict[str, Any] = {"agent": agent_name, "model": agentic.model}

    async def _call() -> tuple[dict[str, Any] | None, dict[str, Any]]:
        try:
            model = agentic.model
            if "/" not in model:
                model = f"{agentic.provider}/{model}"
            response = await litellm.acompletion(
                model=model,
                api_key=agentic.api_key or None,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=agentic.temperature,
                max_tokens=agentic.max_output_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            if content.startswith("{"):
                import json

                return json.loads(content), trace
            return None, trace
        except Exception as exc:
            trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            trace["error"] = str(exc)
            return None, trace

    try:
        return await asyncio.wait_for(_call(), timeout=timeout)
    except asyncio.TimeoutError:
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        trace["error"] = f"timeout after {timeout}s"
        return None, trace


async def enrich_finding_agentic(
    finding: Finding,
    result: ProbeResult,
    config: AppConfig,
    offline_base: EnrichmentResult,
) -> EnrichmentResult:
    target_type = config.target.type.value
    prompt_text = truncate(finding.request_summary)
    response_text = truncate(finding.response_excerpt)
    layers = finding.metadata.get("detection_layers", {})

    user_ctx = (
        f"probe_id: {finding.probe_id}\n"
        f"probe_name: {finding.probe_name}\n"
        f"target_type: {target_type}\n"
        f"severity: {finding.severity.value}\n"
        f"attack_prompt: {prompt_text}\n"
        f"response_excerpt: {response_text}\n"
        f"detection_layers: {layers}\n"
        f"existing_owasp: {finding.owasp}\n"
    )

    trace: list[dict[str, Any]] = []

    triage_raw, triage_trace = await _llm_json(config, TRIAGE_SYSTEM, user_ctx, "triage")
    trace.append(triage_trace)
    triage = TriageResult.model_validate(triage_raw) if isinstance(triage_raw, dict) else None
    category = (triage.category if triage else None) or _default_category(finding.probe_id)

    analyst_sys = ANALYST_SYSTEM.get(category, ANALYST_SYSTEM["other"])
    analyst_raw, analyst_trace = await _llm_json(config, analyst_sys, user_ctx, "analyst")
    trace.append(analyst_trace)
    analyst = None
    if isinstance(analyst_raw, dict):
        analyst = AnalystResult.model_validate(analyst_raw)
        analyst.evidence_quotes = evidence_in_response(
            analyst.evidence_quotes, finding.response_excerpt
        )

    owasp_raw, owasp_trace = await _llm_json(
        config,
        OWASP_SYSTEM,
        user_ctx + f"\nanalyst: {analyst.model_dump() if analyst else {}}",
        "owasp_mapper",
    )
    trace.append(owasp_trace)
    owasp_map = None
    if isinstance(owasp_raw, dict):
        owasp_map = OwaspMappingResult.model_validate(owasp_raw)

    remed_raw, remed_trace = await _llm_json(
        config,
        REMEDIATION_SYSTEM,
        user_ctx + f"\ntarget_type: {target_type}",
        "remediation",
    )
    trace.append(remed_trace)
    remediation = None
    if isinstance(remed_raw, dict):
        remediation = RemediationResult.model_validate(remed_raw)

    synth_raw, synth_trace = await _llm_json(
        config,
        SYNTHESIS_SYSTEM,
        user_ctx
        + f"\nanalyst: {analyst.model_dump() if analyst else {}}\n"
        f"owasp: {owasp_map.model_dump() if owasp_map else {}}",
        "synthesis",
    )
    trace.append(synth_trace)
    synthesis = None
    if isinstance(synth_raw, dict):
        synthesis = SynthesisResult.model_validate(synth_raw)

    payload = {
        "analyst": analyst.model_dump() if analyst else {},
        "owasp": owasp_map.model_dump() if owasp_map else {},
    }
    if not validate_agentic_output(payload, response_excerpt=finding.response_excerpt, allowed_owasp=finding.owasp):
        offline_base.agentic_fallback = True
        return offline_base

    owasp_ids = list(finding.owasp)
    if owasp_map and owasp_map.owasp_ids:
        owasp_ids = list(dict.fromkeys(owasp_map.owasp_ids + owasp_ids))

    remed_steps = list(offline_base.remediation)
    if remediation and remediation.steps:
        remed_steps = remediation.steps

    return EnrichmentResult(
        plain_title=offline_base.plain_title,
        what_happened=synthesis.summary if synthesis and synthesis.summary else offline_base.what_happened,
        why_it_matters=offline_base.why_it_matters,
        owasp=owasp_entries(owasp_ids),
        remediation=remed_steps,
        detection_summary=offline_base.detection_summary,
        agentic_notes=synthesis.analyst_notes if synthesis else (analyst.narrative if analyst else None),
        agent_trace=trace,
        analysis_mode="cloud",
    )


def _default_category(probe_id: str) -> str:
    if probe_id.startswith("agent.") or probe_id.startswith("mcp."):
        return "agency"
    if probe_id.startswith("rag."):
        return "rag"
    if "secret" in probe_id or "hidden" in probe_id or "leak" in probe_id:
        return "disclosure"
    if probe_id.startswith("l1.") or probe_id.startswith("l2.") or probe_id.startswith("l3."):
        return "injection"
    return "other"
