"""Multi-agentic web scan tests (mocked cloud)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.webscan.models import AgentRiskProfile, CapabilityMap, ScanDepth
from agentarmor.webscan.planning.attack_planner import plan_web_attack


def test_multi_agentic_expands_probe_count():
    cap = CapabilityMap(rag=True, mcp=True, tools=["send email"], risk_score=7.0)
    risk = AgentRiskProfile(risk_score=7.0, tool_count=1, rag_enabled=True, mcp_enabled=True)
    standard = plan_web_attack(cap, risk, ScanDepth.STANDARD, ["LLM08", "LLM06"], max_probes=15)
    agentic = plan_web_attack(cap, risk, ScanDepth.MULTI_AGENTIC, ["LLM08", "LLM06"], max_probes=15)
    assert len(agentic) >= len(standard)


def test_multi_agentic_adds_handoff_for_a2a():
    cap = CapabilityMap(a2a=True, tools=["query crm"])
    agentic = plan_web_attack(cap, None, ScanDepth.MULTI_AGENTIC, ["LLM06"], max_probes=30)
    ids = {p.id for p in agentic}
    assert "web.agent.multi-handoff" in ids


@pytest.mark.asyncio
async def test_llm_classifier_returns_candidate():
    from agentarmor.webscan.discovery.llm_classifier import refine_widget_with_llm

    cfg = AppConfig()
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.enabled = True
    cfg.detection.agentic.api_key = "sk-test"

    page = AsyncMock()
    page.evaluate = AsyncMock(
        return_value={"title": "Chat", "inputs": [{"tag": "textarea", "id": "#chat", "cls": "", "placeholder": "Ask"}], "buttons": ["Send"]}
    )

    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content='{"input_selector": "#chat", "send_selector": "button", "confidence": 0.85, "rationale": "found"}'
            )
        )
    ]

    with patch("litellm.acompletion", AsyncMock(return_value=mock_completion)):
        result = await refine_widget_with_llm(page, [], cfg)

    assert result is not None
    assert result.input_selector == "#chat"
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_llm_classifier_skips_offline():
    from agentarmor.webscan.discovery.llm_classifier import refine_widget_with_llm

    cfg = AppConfig()
    page = AsyncMock()
    result = await refine_widget_with_llm(page, [], cfg)
    assert result is None


def test_api_multi_agentic_requires_key():
    from fastapi.testclient import TestClient

    from agentarmor.api.app import app

    client = TestClient(app)
    r = client.post(
        "/v1/web-scans",
        json={
            "page_url": "https://example.com",
            "scan_depth": "multi_agentic",
            "analysis_mode": "cloud",
        },
    )
    if r.status_code == 503:
        pytest.skip("playwright not installed")
    assert r.status_code == 400
    assert "api_key" in r.json()["detail"].lower()
