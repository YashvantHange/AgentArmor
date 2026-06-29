"""Structured evidence spans from detection layer matches."""

from __future__ import annotations

from typing import Any


def collect_evidence_spans(layers: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Aggregate evidence spans from all layers (L1 primary)."""
    if not layers:
        return []

    spans: list[dict[str, Any]] = []

    l1 = layers.get("l1")
    if isinstance(l1, dict):
        for item in l1.get("evidence_spans") or []:
            if isinstance(item, dict):
                spans.append(item)

    for plugin in layers.get("plugins") or []:
        if not isinstance(plugin, dict):
            continue
        evidence = plugin.get("evidence", "")
        if evidence:
            spans.append(
                {
                    "span": evidence[:120],
                    "start": -1,
                    "end": -1,
                    "detector": "plugin",
                    "rule": plugin.get("detector_id", "plugin"),
                    "weight": plugin.get("risk_delta", 0.0),
                }
            )

    echo = layers.get("echo_strip")
    if isinstance(echo, dict):
        for s in echo.get("spans") or []:
            if isinstance(s, dict) and "start" in s and "end" in s:
                spans.append(
                    {
                        "span": "[echo]",
                        "start": s["start"],
                        "end": s["end"],
                        "detector": "echo",
                        "rule": "prompt_echo",
                        "weight": 0.0,
                    }
                )

    return spans
