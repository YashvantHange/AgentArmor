"""Bundled detector — flags obvious secret/token leaks in responses."""

from __future__ import annotations

import re
from typing import Any

from agentarmor.sdk.detector_sdk import Detector, register_detector

_SECRET_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-z0-9_\-]{8,}"),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]{6,}"),
]


@register_detector
class BundledSecretLeakDetector(Detector):
    id = "detector.bundled.secret-leak"
    name = "Secret leak heuristic"

    def analyze(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                return {
                    "risk_delta": 0.12,
                    "evidence": f"secret pattern: {match.group(0)[:60]}",
                }
        return {"risk_delta": 0.0, "evidence": ""}
