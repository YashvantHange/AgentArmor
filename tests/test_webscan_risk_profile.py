"""Risk profile scoring tests."""

from agentarmor.core.config import WebScanRiskWeights
from agentarmor.webscan.discovery.risk_profile import compute_risk_profile
from agentarmor.webscan.models import CapabilityMap, ToolHint


def test_high_risk_combo():
    cap = CapabilityMap(
        framework="Botpress",
        rag=True,
        memory=True,
        mcp=True,
        tools=["send email", "salesforce"],
        agentic_score=0.9,
    )
    tools = [
        ToolHint(name="send email", confidence=0.8),
        ToolHint(name="salesforce", confidence=0.8),
    ]
    profile = compute_risk_profile(cap, tools, external_actions=True, weights=WebScanRiskWeights())
    assert profile.risk_score >= 7.0
    assert profile.rag_enabled
    assert profile.memory_enabled
    assert profile.mcp_enabled
    assert len(profile.risk_reasons) >= 3


def test_low_risk_static():
    cap = CapabilityMap(framework=None, rag=False, memory=False, mcp=False, agentic_score=0.1)
    profile = compute_risk_profile(cap, [], False, WebScanRiskWeights())
    assert profile.risk_score < 4.0


def test_score_bounded():
    cap = CapabilityMap(rag=True, memory=True, mcp=True, a2a=True, agentic_score=1.0)
    tools = [ToolHint(name=f"tool{i}") for i in range(10)]
    profile = compute_risk_profile(cap, tools, True, WebScanRiskWeights())
    assert 0 <= profile.risk_score <= 10
