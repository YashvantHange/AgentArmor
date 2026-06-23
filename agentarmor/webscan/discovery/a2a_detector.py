"""Detect Agent-to-Agent registry and agent card endpoints."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from agentarmor.webscan.models import A2ADetectionResult

_A2A_PATHS = (
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/agents/registry",
    "/api/agents",
)


async def detect_a2a(page: Any, network_log: list[dict[str, Any]], page_url: str) -> A2ADetectionResult:
    """Detect A2A agent cards and multi-agent routing signals."""
    result = A2ADetectionResult()
    for entry in network_log:
        url = (entry.get("url") or "").lower()
        if "agent-card" in url or "/agents/" in url or "handoff" in url:
            result.a2a_enabled = True
            result.confidence = max(result.confidence, 0.65)
            result.registry_urls.append(entry.get("url", ""))

    html = (await page.content()).lower()
    if "agent-card" in html or "a2a" in html or "langgraph" in html or "crewai" in html:
        result.a2a_enabled = True
        result.confidence = max(result.confidence, 0.5)

    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    probe_script = """
    async (paths) => {
      const hits = [];
      for (const p of paths) {
        try {
          const r = await fetch(p, { method: 'GET', credentials: 'same-origin' });
          if (r.ok) hits.push(p);
        } catch (e) {}
      }
      return hits;
    }
    """
    try:
        paths = [urljoin(origin, p) for p in _A2A_PATHS]
        found = await page.evaluate(probe_script, paths)
        for path in found:
            result.a2a_enabled = True
            result.confidence = max(result.confidence, 0.8)
            result.registry_urls.append(str(path))
    except Exception:
        pass

    result.registry_urls = list(dict.fromkeys(result.registry_urls))[:10]
    return result
