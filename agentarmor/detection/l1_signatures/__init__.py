"""L1 fast signature detection — Rust PyO3 with Python fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from agentarmor.detection.l1_signatures.fallback import L1ScanResult, scan as python_scan

logger = logging.getLogger(__name__)
_RUST_AVAILABLE = False
_rust_scan = None


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
    """Signature scan. Python, so the result shape does not depend on the build host.

    This used to dispatch to the Rust extension when it imported. Both engines agree
    on score and matches - the parity test checks that - but the Rust one returns no
    evidence spans, and those carry the matched text, its offsets, the rule, its
    weight, and the owasp and cwe mappings added in 1.4.1. They flow through
    collect_evidence_spans into detection.evidence, which the reports and swarm fact
    extraction read.

    So whether a Rust toolchain happened to be present when the environment was
    built decided whether this function returned evidence. Installing the native
    engine silently made the detection API return less.

    Measured before removing the dispatch, on the 8000-character cap that
    parse_http_body applies to every response, so this is the realistic ceiling
    rather than a synthetic best case:

        payload              python      rust
        typical response    0.14 ms    0.005 ms
        at the 8 KB cap     ~6 ms      ~0.08 ms

    Six milliseconds per probe, against a swarm that is rate-limited to five
    requests a second and spends seconds per probe waiting on a model. Reaching
    parity would mean reimplementing echo-span filtering and the full evidence-span
    metadata in Rust and keeping 31 security rules in lockstep across two languages -
    where a divergence means a rule that fires in one engine and not the other. That
    is not a trade worth making for six milliseconds.

    The crate, its CI job and the parity test all stay: the rules remain in step, so
    wiring it back in later is still possible if it grows evidence spans.
    """
    import time

    start = time.perf_counter()
    result: L1ScanResult = python_scan(text)
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
