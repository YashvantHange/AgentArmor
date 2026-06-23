"""Compute Agent Risk Profile from capability signals."""

from __future__ import annotations

from agentarmor.core.config import WebScanRiskWeights
from agentarmor.webscan.models import AgentRiskProfile, CapabilityMap, ToolHint


def compute_agentic_score(
    tool_count: int,
    rag: bool,
    memory: bool,
    mcp: bool,
    a2a: bool,
) -> float:
    score = min(1.0, tool_count * 0.12)
    if rag:
        score += 0.2
    if memory:
        score += 0.15
    if mcp:
        score += 0.25
    if a2a:
        score += 0.15
    return min(1.0, round(score, 2))


def compute_risk_profile(
    cap: CapabilityMap,
    tools: list[ToolHint],
    external_actions: bool,
    weights: WebScanRiskWeights,
) -> AgentRiskProfile:
    """Score 0–10 executive risk from detected capabilities."""
    factors: dict[str, float] = {}
    tool_count = len(tools)
    raw = 0.0

    tool_factor = min(weights.per_tool_cap, tool_count * weights.per_tool)
    if tool_factor:
        factors["tools"] = tool_factor
        raw += tool_factor

    if cap.rag:
        factors["rag"] = weights.rag
        raw += weights.rag
    if cap.memory:
        factors["memory"] = weights.memory
        raw += weights.memory
    if cap.mcp:
        factors["mcp"] = weights.mcp
        raw += weights.mcp
    if cap.mcp and tool_count > 0:
        factors["mcp_tools_combo"] = weights.mcp_tools_combo
        raw += weights.mcp_tools_combo
    if external_actions:
        factors["external_actions"] = weights.external_actions
        raw += weights.external_actions
    if cap.agentic_score >= weights.high_agentic_threshold:
        factors["high_agentic"] = weights.high_agentic
        raw += weights.high_agentic

    risk_score = min(10.0, round(raw, 1))
    reasons: list[str] = []
    for t in tools[:8]:
        label = t.name.replace("_", " ").title()
        if "email" in t.name.lower():
            reasons.append("Email tool detected")
        elif "salesforce" in t.name.lower() or "crm" in t.name.lower():
            reasons.append("CRM access detected")
        elif "calendar" in t.name.lower() or "meeting" in t.name.lower():
            reasons.append("Calendar/scheduling tool detected")
        elif t.name not in {r.lower() for r in reasons}:
            reasons.append(f"{label} detected")
    if cap.rag and "RAG / knowledge base enabled" not in reasons:
        reasons.append("RAG / knowledge base enabled")
    if cap.memory and "Persistent memory enabled" not in reasons:
        reasons.append("Persistent memory enabled")
    if cap.mcp and "MCP integration enabled" not in reasons:
        reasons.append("MCP integration enabled")
    if cap.a2a and "A2A agent registry detected" not in reasons:
        reasons.append("A2A agent registry detected")
    if external_actions and "External action tools detected" not in reasons:
        reasons.append("External action tools detected")

    if risk_score > 5 and not reasons:
        reasons.append("Multiple agentic capabilities detected")

    return AgentRiskProfile(
        tool_count=tool_count,
        rag_enabled=cap.rag,
        memory_enabled=cap.memory,
        mcp_enabled=cap.mcp,
        external_actions=external_actions,
        agentic_score=cap.agentic_score,
        risk_score=risk_score,
        risk_reasons=reasons[:10],
        risk_factors=factors,
    )


def apply_risk_to_capability_map(cap: CapabilityMap, profile: AgentRiskProfile) -> CapabilityMap:
    cap.risk_score = profile.risk_score
    cap.risk_reasons = list(profile.risk_reasons)
    return cap
