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
    """Warn once that the native engine is absent - only when it actually is.

    ``scan_with_echo_filter`` always uses the Python implementation, because the
    Rust extension exposes ``scan(text)`` and ``rule_count()`` and has no
    echo-aware entry point. That is a correct fallback, but it used to emit
    "Rust L1 engine not installed" unconditionally, telling users who had already
    built the extension to go build it - which is what the shipped installer logs
    on every start.

    The engine being unused on the echo path is a separate matter from it being
    missing, and only the second is the user's to act on.
    """
    global _warned_fallback
    if _RUST_AVAILABLE:
        return
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
    evidence_spans: list[dict] | None = None


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
        evidence_spans=list(result.evidence_spans or []),
    )


def scan_with_echo_filter(text: str, echo_spans: list | None) -> L1Result:
    """Echo-aware scan. Python only, by necessity rather than by choice.

    The Rust extension exports ``scan(text)`` and ``rule_count()``; it has no
    entry point that accepts echo spans, so there is nothing to dispatch to here.
    This is the path ``detection/pipeline.py`` uses, which means the native engine
    is currently unused by a scan even when it is compiled and importable - only
    the detection API's direct ``scan()`` reaches it.
    """
    import time

    start = time.perf_counter()
    result: L1ScanResult = python_scan(text, echo_spans=echo_spans)
    _warn_fallback_once()
    latency_ms = (time.perf_counter() - start) * 1000
    return L1Result(
        score=result.score,
        matches=result.matches,
        categories=result.categories,
        engine=result.engine,
        latency_ms=latency_ms,
        evidence_spans=list(result.evidence_spans or []),
    )


def rust_available() -> bool:
    return _RUST_AVAILABLE
