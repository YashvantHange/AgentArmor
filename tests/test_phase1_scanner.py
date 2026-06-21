"""Phase 1 tests — profiles, assertions, plugins, outcomes."""

from __future__ import annotations

import pytest

from agentarmor.core.config import AppConfig, EndpointEngineConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult, Target
from agentarmor.detection.assertions import composite_vuln_score, run_assertions
from agentarmor.detection.l4_structural.injection_outcomes import analyze_injection_outcomes
from agentarmor.detection.pipeline import analyze_probe_result
from agentarmor.engines.endpoint.profiles import (
    build_payload,
    extract_response_text,
    looks_like_page_url,
    parse_http_body,
)
from agentarmor.orchestrator.plugins.registry import filter_probes_by_plugins
from agentarmor.orchestrator.runner import RunnableProbe


def test_looks_like_page_url():
    assert looks_like_page_url("https://dvllm.com/lab-themes/llm01-low/index.html")
    assert not looks_like_page_url("https://api.example.com/v1/chat/completions")


def test_extract_response_openai_shape():
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert extract_response_text(data, None) == "hello"


def test_extract_response_custom_path():
    data = {"reply": "pong"}
    assert extract_response_text(data, "reply") == "pong"


def test_build_payload_openai():
    cfg = AppConfig(target=Target(url="http://x"), engine_endpoint=EndpointEngineConfig(profile="openai"))
    body, pid = build_payload(cfg, ProbeRequest(messages=[{"role": "user", "content": "hi"}]))
    assert pid == "openai"
    assert body["messages"][0]["content"] == "hi"


def test_parse_http_body_rejects_html():
    content, err = parse_http_body(
        status_code=200,
        content_type="text/html",
        raw_text="<html><body>ShopBot</body></html>",
        data={},
        response_path=None,
    )
    assert content == ""
    assert err and "HTML" in err


def test_parse_http_body_rejects_404():
    content, err = parse_http_body(
        status_code=404,
        content_type="application/json",
        raw_text="not found",
        data={},
        response_path=None,
    )
    assert err and "404" in err


def test_injection_outcome_admin_code():
    score, ev = analyze_injection_outcomes(
        "l1.ignore-instructions",
        "ignore rules",
        "Here is your ADMIN90OFF discount code for 90% off.",
    )
    assert score >= 0.85
    assert ev


def test_assertions_flag_leak():
    results = run_assertions(
        probe_id="l1.ignore-instructions",
        prompt="ignore",
        response="ADMIN DISCOUNT REVEALED code ADMIN90OFF",
    )
    score = composite_vuln_score(results)
    assert score >= 0.7


def test_connectivity_error_warns_not_pass(detection_config):
    result = ProbeResult(
        probe_id="l1.ignore-instructions",
        probe_name="x",
        request=ProbeRequest(messages=[]),
        response=ProbeResponse(content=""),
        error="HTTP 404",
    )
    detection = analyze_probe_result(result, config=detection_config)
    assert detection.decision.value == "WARN"
    assert "connectivity" in detection.layers


def test_plugin_filter_injection():
    probes = [
        RunnableProbe("l1.ignore-instructions", "A", ["LLM01"], "L1"),
        RunnableProbe("l1.reveal-system-prompt", "B", ["LLM02"], "L1"),
        RunnableProbe("mcp.tool-enumeration", "C", ["LLM06"], "mcp"),
    ]
    filtered = filter_probes_by_plugins(probes, ["security:prompt-injection"])
    ids = {p.id for p in filtered}
    assert "l1.ignore-instructions" in ids
    assert "l1.reveal-system-prompt" not in ids


@pytest.mark.asyncio
async def test_judge_apply_merges_cloud_verdict():
    from agentarmor.core.models import Decision
    from agentarmor.detection.agentic.judge import JudgeResult, apply_judge_to_detection

    judge = JudgeResult(vulnerable=True, confidence=0.9, evidence_quotes=["ADMIN90OFF"])
    risk, decision, sev = apply_judge_to_detection(0.2, Decision.PASS, judge)
    assert decision == Decision.FAIL
    assert risk >= 0.85
    assert sev is not None
