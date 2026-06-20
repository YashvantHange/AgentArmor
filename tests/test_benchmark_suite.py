"""Benchmark suite loader tests."""

from agentarmor.benchmark.suite_loader import load_suite, resolve_suite_probes


def test_load_owasp_suite():
    suite = load_suite("owasp")
    assert suite.id == "owasp-llm-v1"
    assert len(suite.categories) == 5
    ids = {c.id for c in suite.categories}
    assert "LLM01" in ids
    assert "LLM06" in ids


def test_resolve_probes():
    suite = load_suite("owasp")
    probes = resolve_suite_probes(suite)
    assert len(probes) >= 10
    assert any(p.probe_id == "l1.ignore-instructions" for p in probes)
    assert any(p.multi_turn is not None for p in probes)
