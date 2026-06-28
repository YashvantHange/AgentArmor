"""Tests for assertion composite scoring."""

from agentarmor.detection.assertions import AssertionResult, composite_vuln_score


def test_composite_vuln_score_all_passed():
    results = [
        AssertionResult(passed=True, assertion_type="non-empty", score=0.0),
        AssertionResult(passed=True, assertion_type="refusal", score=0.1),
    ]
    assert composite_vuln_score(results) == 0.0


def test_composite_vuln_score_uses_max_failed():
    results = [
        AssertionResult(passed=True, assertion_type="non-empty", score=0.0),
        AssertionResult(passed=False, assertion_type="refusal", score=0.75),
    ]
    assert composite_vuln_score(results) == 0.75
