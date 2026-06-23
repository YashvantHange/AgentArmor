"""Detect agent tools from DOM and network traffic."""

from __future__ import annotations

import json
import re
from typing import Any

from agentarmor.webscan.models import ToolHint

_TOOL_KEYWORDS = re.compile(
    r"\b(book meeting|send email|create ticket|query crm|salesforce|calendar|"
    r"delete|payment|execute|run tool|call tool)\b",
    re.I,
)

_EXTERNAL_ACTION_WORDS = frozenset(
    {"email", "send", "payment", "delete", "crm", "salesforce", "sms", "transfer"}
)

TOOL_DOM_SCRIPT = """
() => {
  const patterns = [
    'book meeting', 'send email', 'create ticket', 'query crm', 'salesforce',
    'calendar', 'schedule', 'crm', 'email', 'delete', 'payment'
  ];
  const found = [];
  const textNodes = document.querySelectorAll(
    'button, [role="button"], [class*="action"], [class*="tool"], [class*="chip"], a'
  );
  textNodes.forEach(el => {
    const t = ((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
    for (const p of patterns) {
      if (t.includes(p) && !found.some(f => f.name === p)) {
        found.push({ name: p, source: 'dom', confidence: 0.7 });
      }
    }
  });
  return found.slice(0, 20);
}
"""


def detect_tools_from_network(network_log: list[dict[str, Any]]) -> list[ToolHint]:
    hints: list[ToolHint] = []
    seen: set[str] = set()
    for entry in network_log:
        url = (entry.get("url") or "").lower()
        if "tools" in url or "function" in url or "mcp" in url:
            hints.append(ToolHint(name="api_tools_endpoint", source="network", confidence=0.6))
        body_hint = str(entry)
        for match in _TOOL_KEYWORDS.finditer(body_hint):
            name = match.group(0).lower()
            if name not in seen:
                seen.add(name)
                hints.append(ToolHint(name=name, source="network", confidence=0.55))
    return hints


async def detect_tools(page: Any, network_log: list[dict[str, Any]]) -> list[ToolHint]:
    """Find tool/action hints in DOM and captured network metadata."""
    raw: list[dict] = await page.evaluate(TOOL_DOM_SCRIPT)
    hints = [ToolHint(**item) for item in raw]
    hints.extend(detect_tools_from_network(network_log))
    deduped: dict[str, ToolHint] = {}
    for h in hints:
        key = h.name.lower()
        if key not in deduped or h.confidence > deduped[key].confidence:
            deduped[key] = h
    return list(deduped.values())


def has_external_actions(tools: list[ToolHint]) -> bool:
    for t in tools:
        name = t.name.lower()
        if any(w in name for w in _EXTERNAL_ACTION_WORDS):
            return True
    return False
