"""L2 heuristic classifier when ONNX model is not available."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentarmor.detection.rules.catalog import l2_fallback_rules

L2_CLASSES = [
    "prompt_injection",
    "data_leakage",
    "jailbreak",
    "tool_abuse",
    "unsafe_output",
]

_RULES: list[tuple[str, str, float]] = l2_fallback_rules()


@dataclass
class L2Result:
    scores: dict[str, float] = field(default_factory=dict)
    max_score: float = 0.0
    top_class: str = "prompt_injection"
    latency_ms: float = 0.0
    engine: str = "fallback"


def classify_fallback(text: str) -> L2Result:
    import time

    start = time.perf_counter()
    scores = {c: 0.0 for c in L2_CLASSES}
    for pattern, cls, weight in _RULES:
        if re.search(pattern, text):
            scores[cls] = max(scores[cls], weight)
    top_class = max(scores, key=scores.get)  # type: ignore[arg-type]
    max_score = scores[top_class]
    latency_ms = (time.perf_counter() - start) * 1000
    return L2Result(
        scores=scores,
        max_score=max_score,
        top_class=top_class,
        latency_ms=latency_ms,
        engine="fallback",
    )
