"""Shannon entropy analysis for encoded or obfuscated outputs."""

from __future__ import annotations

import math
from collections import Counter


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def analyze_entropy(text: str, spike_threshold: float = 4.8) -> tuple[float, list[str]]:
    """Return (score 0-1, evidence). High entropy may indicate encoding/obfuscation."""
    if len(text) < 40:
        return 0.0, []

    entropy = shannon_entropy(text)
    evidence: list[str] = []
    score = 0.0

    if entropy >= spike_threshold:
        score = min(1.0, (entropy - spike_threshold) / 2.0 + 0.3)
        evidence.append(f"high character entropy: {entropy:.2f}")

    # Base64-like long tokens
    tokens = text.split()
    b64_like = [t for t in tokens if len(t) >= 20 and t.isalnum() and any(c.isdigit() for c in t)]
    if b64_like:
        score = max(score, 0.5)
        evidence.append(f"possible encoded tokens: {len(b64_like)}")

    return min(score, 1.0), evidence
