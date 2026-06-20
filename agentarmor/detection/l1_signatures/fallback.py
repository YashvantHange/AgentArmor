"""L1 signature rules — Python fallback when Rust extension is not built."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentarmor.detection.l1_signatures.patterns import SIGNATURE_RULES


@dataclass
class L1ScanResult:
    score: float
    matches: list[str]
    categories: list[str]
    engine: str = "python"


def scan(text: str) -> L1ScanResult:
    score = 0.0
    matches: list[str] = []
    categories: list[str] = []

    for rule in SIGNATURE_RULES:
        if rule.pattern.search(text):
            score = max(score, rule.weight)
            matches.append(rule.name)
            if rule.category not in categories:
                categories.append(rule.category)

    return L1ScanResult(score=score, matches=matches, categories=categories, engine="python")
