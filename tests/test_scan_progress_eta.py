"""P0 tests for scan progress duration formatting (mirrors GUI utils)."""

from __future__ import annotations

# Python mirror of gui/src/lib/scanProgressUtils.ts for CI without Node


def format_duration_ms(ms: int) -> str:
    total_seconds = max(0, ms) // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def eta_confidence(completed_units: int) -> str:
    if completed_units < 2:
        return "none"
    if completed_units < 5:
        return "low"
    if completed_units < 15:
        return "medium"
    return "high"


def test_format_duration_hours():
    assert format_duration_ms(19_839_000) == "5:30:39"


def test_format_duration_minutes_only():
    assert format_duration_ms(90_000) == "1:30"


def test_eta_confidence_bands():
    assert eta_confidence(1) == "none"
    assert eta_confidence(4) == "low"
    assert eta_confidence(10) == "medium"
    assert eta_confidence(20) == "high"
