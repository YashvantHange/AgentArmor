"""Detect persistent memory / personalization features."""

from __future__ import annotations

from typing import Any

from agentarmor.webscan.models import MemoryDetectionResult

_MEMORY_PHRASES = (
    "remember this",
    "my preferences",
    "conversation history",
    "persistent memory",
    "enable memory",
    "clear memory",
    "saved memories",
    "personalization",
)

MEMORY_DOM_SCRIPT = """
(phrases) => {
  const found = [];
  const body = (document.body.innerText || '').toLowerCase();
  for (const p of phrases) {
    if (body.includes(p)) found.push(p);
  }
  document.querySelectorAll('[class*="memory"], [id*="memory"], [data-testid*="memory"]').forEach(el => {
    found.push('memory_ui_element');
  });
  return [...new Set(found)];
}
"""

STORAGE_SCRIPT = """
() => {
  const keys = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i) || '';
      if (/memory|preference|history|user_profile|chat_history/i.test(k)) keys.push(k);
    }
  } catch (e) {}
  return keys.slice(0, 10);
}
"""


def _network_memory_signals(network_log: list[dict[str, Any]]) -> list[str]:
    indicators: list[str] = []
    for entry in network_log:
        url = (entry.get("url") or "").lower()
        if any(p in url for p in ("/memory", "/preferences", "/user/context", "/session/history")):
            indicators.append(url.split("?")[0][-80:])
    return indicators


async def detect_memory(page: Any, network_log: list[dict[str, Any]]) -> MemoryDetectionResult:
    """Detect memory/personalization from UI copy, storage keys, and network."""
    result = MemoryDetectionResult()
    dom_indicators: list[str] = await page.evaluate(MEMORY_DOM_SCRIPT, list(_MEMORY_PHRASES))
    storage_keys: list[str] = await page.evaluate(STORAGE_SCRIPT)
    net_indicators = _network_memory_signals(network_log)

    all_indicators = list(dict.fromkeys(dom_indicators + storage_keys + net_indicators))
    result.indicators = all_indicators[:20]
    result.memory_enabled = len(all_indicators) > 0
    if result.memory_enabled:
        result.confidence = min(1.0, 0.4 + 0.15 * len(all_indicators))
    return result
