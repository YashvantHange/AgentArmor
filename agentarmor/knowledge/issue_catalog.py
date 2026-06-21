"""Static issue knowledge catalog for offline enrichment."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).with_name("issue_catalog.json")

_DEFAULT_ENTRY = {
    "plain_title": "Security issue detected",
    "what_happened": "An automated security probe identified potentially unsafe behavior.",
    "why_it_matters": "This weakness may allow attackers to bypass policies or extract sensitive data.",
    "remediation": [
        "Review system prompts and safety guardrails.",
        "Add output filtering and policy enforcement.",
        "Re-test after applying fixes.",
    ],
}


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict[str, Any]]:
    if _CATALOG_PATH.exists():
        return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {}


def get_probe_entry(probe_id: str) -> dict[str, Any]:
    catalog = load_catalog()
    entry = dict(catalog.get(probe_id, catalog.get("_default", _DEFAULT_ENTRY)))
    if not entry.get("plain_title"):
        entry["plain_title"] = _DEFAULT_ENTRY["plain_title"]
    return entry


def format_entry(
    probe_id: str,
    *,
    target_type: str,
    probe_name: str,
    response_excerpt: str = "",
) -> dict[str, Any]:
    entry = get_probe_entry(probe_id)
    subject = _subject_for_target(target_type)
    what = entry.get("what_happened", _DEFAULT_ENTRY["what_happened"])
    if "{subject}" in what:
        what = what.format(subject=subject)
    title = entry.get("plain_title", probe_name)
    if response_excerpt and len(response_excerpt) > 20:
        what = f"{what} Response excerpt: {response_excerpt[:200]}..."
    return {
        "plain_title": title,
        "what_happened": what,
        "why_it_matters": entry.get("why_it_matters", _DEFAULT_ENTRY["why_it_matters"]),
        "remediation": list(entry.get("remediation", _DEFAULT_ENTRY["remediation"])),
        "target_types": entry.get("target_types", []),
    }


def _subject_for_target(target_type: str) -> str:
    return {
        "endpoint": "The API model",
        "provider": "The cloud model",
        "local": "The local model",
        "agent": "The agent framework",
        "mcp": "The MCP server",
        "rag": "The RAG retrieval system",
    }.get(target_type, "The target")
