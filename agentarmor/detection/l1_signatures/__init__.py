"""L1 fast signature detection — Rust PyO3 with Python fallback."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

from agentarmor.detection.l1_signatures.fallback import L1ScanResult, scan as python_scan

logger = logging.getLogger(__name__)
_RUST_AVAILABLE = False
_rust_scan = None
_warned_fallback = False


def _warn_fallback_once() -> None:
    global _warned_fallback
    if not _warned_fallback:
        warnings.warn(
            "Rust L1 engine not installed; using Python fallback. "
            "Build with: cd native/l1_signatures && maturin develop --release",
            stacklevel=2,
        )
        _warned_fallback = True


try:
    from _l1_signatures import scan as _rust_scan_fn  # type: ignore[import-not-found]

    _rust_scan = _rust_scan_fn
    _RUST_AVAILABLE = True
except ImportError:
    pass


@dataclass
class L1Result:
    score: float
    matches: list[str]
    categories: list[str]
    engine: str
    latency_ms: float = 0.0


def scan(text: str) -> L1Result:
    import time

    start = time.perf_counter()
    if _RUST_AVAILABLE and _rust_scan is not None:
        raw = _rust_scan(text)
        latency_ms = (time.perf_counter() - start) * 1000
        return L1Result(
            score=float(raw["score"]),
            matches=list(raw["matches"]),
            categories=list(raw["categories"]),
            engine="rust",
            latency_ms=latency_ms,
        )

    result: L1ScanResult = python_scan(text)
    _warn_fallback_once()
    latency_ms = (time.perf_counter() - start) * 1000
    return L1Result(
        score=result.score,
        matches=result.matches,
        categories=result.categories,
        engine=result.engine,
        latency_ms=latency_ms,
    )


def rust_available() -> bool:
    return _RUST_AVAILABLE
