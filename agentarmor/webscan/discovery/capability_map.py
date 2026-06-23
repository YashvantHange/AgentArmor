"""Merge discovery detectors into CapabilityMap."""

from __future__ import annotations

from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.webscan.discovery.a2a_detector import detect_a2a
from agentarmor.webscan.discovery.memory_detector import detect_memory
from agentarmor.webscan.discovery.mcp_detector import detect_mcp
from agentarmor.webscan.discovery.risk_profile import (
    apply_risk_to_capability_map,
    compute_agentic_score,
    compute_risk_profile,
)
from agentarmor.webscan.discovery.tool_detector import detect_tools, has_external_actions
from agentarmor.webscan.models import AgentRiskProfile, CapabilityMap, ToolHint

RAG_DOM_SCRIPT = """
() => {
  const text = (document.body.innerText || '').toLowerCase();
  const markers = [
    'knowledge base', 'search documents', 'website search', 'sources', 'citations',
    'retrieval', 'search your', 'document search'
  ];
  return markers.filter(m => text.includes(m));
}
"""


async def detect_rag_signals(page: Any, network_log: list[dict[str, Any]]) -> bool:
    dom_hits: list[str] = await page.evaluate(RAG_DOM_SCRIPT)
    if dom_hits:
        return True
    for entry in network_log:
        url = (entry.get("url") or "").lower()
        if any(p in url for p in ("/retrieve", "/search", "/embeddings", "pinecone", "weaviate", "qdrant")):
            return True
    return False


async def build_capability_map(
    page: Any,
    network_log: list[dict[str, Any]],
    page_url: str,
    framework: str | None,
    config: AppConfig,
) -> tuple[CapabilityMap, AgentRiskProfile, list[ToolHint]]:
    """Run all capability detectors and compute risk profile."""
    tools = await detect_tools(page, network_log)
    mcp = await detect_mcp(page, network_log, page_url)
    memory = await detect_memory(page, network_log)
    a2a = await detect_a2a(page, network_log, page_url)
    rag = await detect_rag_signals(page, network_log)

    tool_names = [t.name for t in tools]
    cap = CapabilityMap(
        framework=framework,
        rag=rag,
        memory=memory.memory_enabled,
        mcp=mcp.mcp_enabled,
        a2a=a2a.a2a_enabled,
        tools=tool_names,
        mcp_servers=mcp.servers[:10],
        memory_indicators=memory.indicators[:10],
        agentic_score=compute_agentic_score(
            len(tools), rag, memory.memory_enabled, mcp.mcp_enabled, a2a.a2a_enabled
        ),
    )
    profile = compute_risk_profile(
        cap,
        tools,
        has_external_actions(tools),
        config.webscan.risk_weights,
    )
    apply_risk_to_capability_map(cap, profile)
    return cap, profile, tools
