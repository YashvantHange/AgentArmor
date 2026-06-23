"""Probe catalog tests."""

from agentarmor.webscan.probes.catalog import get_web_probes


def test_default_probes_include_owasp_tags():
    probes = get_web_probes()
    assert len(probes) >= 5
    tags = {o for p in probes for o in p.owasp}
    assert "LLM01" in tags
    assert "LLM08" in tags


def test_owasp_filter():
    probes = get_web_probes(owasp_filters=["LLM07"])
    assert all("LLM07" in p.owasp for p in probes)
    assert len(probes) >= 2
