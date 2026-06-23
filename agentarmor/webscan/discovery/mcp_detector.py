"""Detect MCP endpoints and JSON-RPC patterns."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from agentarmor.webscan.models import MCPDetectionResult

_MCP_METHODS = frozenset(
    {
        "tools/list",
        "tools/call",
        "resources/list",
        "prompts/list",
        "initialize",
        "notifications/",
    }
)

_MCP_PATHS = ("/mcp", "/mcp.json", "/.well-known/mcp", "/tools/registry")

MCP_DOM_SCRIPT = """
() => {
  const hints = [];
  const html = document.documentElement.innerHTML.toLowerCase();
  if (html.includes('mcp') || html.includes('modelcontextprotocol')) hints.push('page_mcp_marker');
  const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src.toLowerCase());
  if (scripts.some(s => s.includes('mcp') || s.includes('modelcontextprotocol'))) hints.push('mcp_script');
  try {
    if (window.__MCP__ !== undefined) hints.push('global_mcp');
  } catch (e) {}
  return hints;
}
"""


def _scan_network_for_mcp(network_log: list[dict[str, Any]]) -> MCPDetectionResult:
    result = MCPDetectionResult()
    for entry in network_log:
        url = entry.get("url") or ""
        url_lower = url.lower()
        if any(p in url_lower for p in _MCP_PATHS):
            result.mcp_enabled = True
            result.confidence = max(result.confidence, 0.7)
            result.servers.append(url)
        if "jsonrpc" in url_lower or "mcp" in url_lower:
            result.jsonrpc_detected = True
            result.confidence = max(result.confidence, 0.5)
        for method in _MCP_METHODS:
            if method in url_lower:
                result.methods_observed.append(method)
                result.mcp_enabled = True
                result.confidence = max(result.confidence, 0.65)
    result.servers = list(dict.fromkeys(result.servers))[:10]
    result.methods_observed = list(dict.fromkeys(result.methods_observed))
    return result


async def detect_mcp(
    page: Any,
    network_log: list[dict[str, Any]],
    page_url: str,
) -> MCPDetectionResult:
    """Detect MCP from DOM markers, network log, and same-origin well-known paths."""
    result = _scan_network_for_mcp(network_log)
    dom_hints: list[str] = await page.evaluate(MCP_DOM_SCRIPT)
    if dom_hints:
        result.mcp_enabled = True
        result.confidence = max(result.confidence, 0.55 + 0.1 * len(dom_hints))
        result.servers.extend(dom_hints)

    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    probe_script = """
    async (paths) => {
      const hits = [];
      for (const p of paths) {
        try {
          const r = await fetch(p, { method: 'HEAD', credentials: 'same-origin' });
          if (r.ok || r.status === 405) hits.push(p);
        } catch (e) {}
      }
      return hits;
    }
    """
    try:
        paths = [urljoin(origin, p) for p in _MCP_PATHS]
        found = await page.evaluate(probe_script, paths)
        for path in found:
            result.mcp_enabled = True
            result.confidence = max(result.confidence, 0.75)
            result.servers.append(str(path))
    except Exception:
        pass

    result.servers = list(dict.fromkeys(result.servers))[:15]
    return result
