"""Prompt echo detection — input substrings appearing in model output."""

from __future__ import annotations


def _longest_shared_substring(a: str, b: str, min_len: int = 12) -> str:
    a_lower, b_lower = a.lower(), b.lower()
    best = ""
    for i in range(len(a_lower)):
        for j in range(i + min_len, len(a_lower) + 1):
            fragment = a_lower[i:j]
            if len(fragment) >= min_len and fragment in b_lower and len(fragment) > len(best):
                best = fragment
    return best


def analyze_echo(prompt: str, response: str, min_len: int = 12) -> tuple[float, list[str]]:
    if not prompt or not response:
        return 0.0, []

    shared = _longest_shared_substring(prompt, response, min_len=min_len)
    evidence: list[str] = []
    score = 0.0

    if shared:
        ratio = len(shared) / max(len(prompt), 1)
        if ratio > 0.5:
            score = 0.7
            evidence.append(f"large prompt echo ({len(shared)} chars, {ratio:.0%} of prompt)")
        elif ratio > 0.25:
            score = 0.45
            evidence.append(f"moderate prompt echo ({len(shared)} chars)")

    # Suspicious: system-style echo in response
    if "you are a" in response.lower() and "you are a" in prompt.lower():
        score = max(score, 0.55)
        evidence.append("role definition echoed in output")

    return min(score, 1.0), evidence
