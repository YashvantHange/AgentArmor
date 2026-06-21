"""Red-team plugin registry — filters probes by security category."""

from __future__ import annotations

from typing import Protocol


class _ProbeLike(Protocol):
    id: str
    layer: str

# Probe IDs included per plugin (prefix / exact match)
_PLUGIN_PROBE_RULES: dict[str, list[str]] = {
    "security:prompt-injection": [
        "l1.ignore-instructions",
        "l1.act-as-root",
        "l2.",
        "l3.",
    ],
    "security:disclosure": [
        "l1.reveal-system-prompt",
        "l1.hidden-rules",
    ],
    "trust:refusal-bypass": [
        "l2.roleplay",
        "l2.encoding-base64",
        "l2.translation",
        "l2.indirect-injection",
        "l2.context-split",
        "l3.crescendo",
        "l3.gradual-escalation",
        "l3.tap",
        "l3.goat",
    ],
    "custom:intent": [],  # populated via custom probes only
}

DEFAULT_PLUGINS = [
    "security:prompt-injection",
    "security:disclosure",
    "trust:refusal-bypass",
]


def filter_probes_by_plugins(
    probes: list[_ProbeLike],
    plugin_ids: list[str] | None,
) -> list[_ProbeLike]:
    if not plugin_ids:
        plugin_ids = list(DEFAULT_PLUGINS)

    allowed_ids: set[str] = set()
    allow_all = False
    for pid in plugin_ids:
        if pid == "all":
            allow_all = True
            break
        rules = _PLUGIN_PROBE_RULES.get(pid, [])
        for rule in rules:
            if rule.endswith("."):
                for p in probes:
                    if p.id.startswith(rule):
                        allowed_ids.add(p.id)
            else:
                allowed_ids.add(rule)

    if allow_all:
        return probes

    # Always include plugin-layer custom probes when custom:intent selected
    if "custom:intent" in plugin_ids:
        return [p for p in probes if p.id in allowed_ids or p.layer == "plugin"]

    if not allowed_ids:
        return probes

    filtered = [p for p in probes if p.id in allowed_ids or _matches_prefix(p.id, plugin_ids)]
    return filtered or probes


def _matches_prefix(probe_id: str, plugin_ids: list[str]) -> bool:
    for pid in plugin_ids:
        for rule in _PLUGIN_PROBE_RULES.get(pid, []):
            if rule.endswith(".") and probe_id.startswith(rule):
                return True
            if probe_id == rule:
                return True
    return False


def list_plugins() -> list[dict[str, str]]:
    return [
        {"id": k, "description": _plugin_description(k)}
        for k in _PLUGIN_PROBE_RULES
    ]


def _plugin_description(plugin_id: str) -> str:
    descriptions = {
        "security:prompt-injection": "Instruction override and injection probes (L1–L3)",
        "security:disclosure": "System prompt and hidden policy leakage",
        "trust:refusal-bypass": "Jailbreak, encoding, and multi-turn bypass strategies",
        "custom:intent": "User-defined seed prompts via plugins",
    }
    return descriptions.get(plugin_id, plugin_id)
