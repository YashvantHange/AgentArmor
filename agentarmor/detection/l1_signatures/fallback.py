"""L1 signature rules — Python fallback when Rust extension is not built."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentarmor.detection.l1_signatures.patterns import SIGNATURE_RULES


@dataclass
class L1ScanResult:
    score: float
    matches: list[str]
    categories: list[str]
    engine: str = "python"
    evidence_spans: list[dict] = field(default_factory=list)


def scan(text: str, echo_spans: list | None = None) -> L1ScanResult:
    score = 0.0
    matches: list[str] = []
    categories: list[str] = []
    evidence_spans: list[dict] = []

    for rule in SIGNATURE_RULES:
        kept = False
        chosen = None
        for match in rule.pattern.finditer(text):
            if echo_spans and _match_in_echo_only(match.start(), match.end(), echo_spans):
                continue
            kept = True
            chosen = match
            break
        if kept and chosen is not None:
            score = max(score, rule.weight)
            matches.append(rule.name)
            if rule.category not in categories:
                categories.append(rule.category)
            evidence_spans.append(
                {
                    "span": chosen.group(0),
                    "start": chosen.start(),
                    "end": chosen.end(),
                    "detector": "L1",
                    "rule": rule.name,
                    "weight": rule.weight,
                }
            )

    return L1ScanResult(
        score=score,
        matches=matches,
        categories=categories,
        evidence_spans=evidence_spans,
        engine="python",
    )


def _match_in_echo_only(start: int, end: int, echo_spans: list) -> bool:
    from agentarmor.detection.l4_structural.echo import EchoSpan, match_fully_inside_echo

    spans = [
        s if isinstance(s, EchoSpan) else EchoSpan(s[0], s[1], "")
        for s in echo_spans
    ]
    return match_fully_inside_echo(start, end, spans)
