"""Layer 2 — chatbot framework fingerprint detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentarmor.webscan.discovery.dom_scanner import FRAMEWORK_DETECT_SCRIPT
from agentarmor.webscan.models import WidgetCandidate


def _frameworks_path() -> Path:
    return Path(__file__).with_name("frameworks.json")


def load_frameworks_config() -> dict[str, Any]:
    return json.loads(_frameworks_path().read_text(encoding="utf-8"))


def get_chat_keywords() -> list[str]:
    return list(load_frameworks_config().get("chat_keywords", []))


async def detect_framework(page: Any) -> dict[str, Any] | None:
    providers = load_frameworks_config().get("providers", [])
    return await page.evaluate(FRAMEWORK_DETECT_SCRIPT, providers)


def boost_candidates_for_framework(
    candidates: list[WidgetCandidate],
    framework: dict[str, Any] | None,
) -> list[WidgetCandidate]:
    if not framework or framework.get("score", 0) < 2:
        return candidates
    fw_name = framework.get("name")
    input_hints: list[str] = list(framework.get("input_hints") or [])
    boosted: list[WidgetCandidate] = []
    for c in candidates:
        data = c.model_copy(deep=True)
        data.framework = fw_name
        data.confidence = min(1.0, data.confidence + 0.15 * min(framework["score"], 4) / 4)
        data.score_breakdown = {**data.score_breakdown, "framework": framework["score"]}
        for hint in input_hints:
            if hint and (c.input_selector == hint or hint in c.input_selector):
                data.confidence = min(1.0, data.confidence + 0.2)
                data.score_breakdown = {**data.score_breakdown, "input_hint": 1.0}
                break
        boosted.append(data)
    boosted.sort(key=lambda x: x.confidence, reverse=True)
    return boosted
