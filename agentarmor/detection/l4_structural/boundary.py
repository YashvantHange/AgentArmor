"""Boundary violation detection — delimiter / role marker leaks in output."""

from __future__ import annotations

import re

_BOUNDARY_PATTERNS = [
    (re.compile(r"<<SYS>>|<<sys>>"), "llama_sys_delimiter", 0.75),
    (re.compile(r"\[INST\]|\[/INST\]"), "llama_inst_delimiter", 0.75),
    (re.compile(r"<\|im_start\|>|<\|im_end\|>"), "chatml_delimiter", 0.80),
    (re.compile(r"###\s*(System|Human|Assistant)\s*:"), "role_header_leak", 0.70),
    (re.compile(r"(?i)\brole:\s*(system|user|assistant)\b"), "role_field_leak", 0.65),
    (re.compile(r"(?i)BEGIN\s+SYSTEM|END\s+SYSTEM"), "system_block_leak", 0.80),
]


def analyze_boundary(response: str) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []

    for pattern, name, weight in _BOUNDARY_PATTERNS:
        if pattern.search(response):
            score = max(score, weight)
            evidence.append(f"boundary violation: {name}")

    return score, evidence
