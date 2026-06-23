"""Stable response model tests."""

from agentarmor.webscan.models import StableResponse


def test_stable_response_defaults():
    s = StableResponse(text="hello", complete=True, wait_ms=100.0)
    assert not s.partial
    assert not s.stream_detected
