"""L2 heuristic classifier when ONNX model is not available."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

L2_CLASSES = [
    "prompt_injection",
    "data_leakage",
    "jailbreak",
    "tool_abuse",
    "unsafe_output",
]

_RULES: list[tuple[str, str, float]] = [
    (r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions", "prompt_injection", 0.9),
    (r"(?i)disregard\s+(your\s+)?(system\s+)?prompt", "prompt_injection", 0.85),
    (r"(?i)my\s+system\s+prompt\s+is", "data_leakage", 0.88),
    (r"(?i)system\s*prompt\s*(is|:)", "data_leakage", 0.85),
    (r"(?i)hidden\s+rules?", "data_leakage", 0.8),
    (r"(?i)\bDAN\b|do\s+anything\s+now", "jailbreak", 0.92),
    (r"(?i)developer\s+mode|uncensored|no\s+restrictions", "jailbreak", 0.85),
    (r"(?i)tool\s*call|invoke\s+tool|delete_all", "tool_abuse", 0.8),
    (r"(?i)api[_\s]?key|password|secret", "unsafe_output", 0.75),
    (r"(?i)bypass\s+(content\s+)?filter", "unsafe_output", 0.7),
]


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
