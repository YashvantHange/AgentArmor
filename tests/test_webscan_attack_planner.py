"""Probe selection rules tests."""

from agentarmor.webscan.models import CapabilityMap
from agentarmor.webscan.planning.rules import select_probes_for_capabilities


def test_rag_probes_added():
    cap = CapabilityMap(rag=True)
    probes = select_probes_for_capabilities(cap, ["LLM08"], max_probes=20)
    ids = {p.id for p in probes}
    assert any(i.startswith("web.rag.") for i in ids)


def test_tool_probes_added():
    cap = CapabilityMap(tools=["send email"])
    probes = select_probes_for_capabilities(cap, ["LLM06"], max_probes=20)
    ids = {p.id for p in probes}
    assert any("tool-abuse" in i for i in ids)


def test_memory_probes_added():
    cap = CapabilityMap(memory=True)
    probes = select_probes_for_capabilities(cap, ["LLM01"], max_probes=20)
    ids = {p.id for p in probes}
    assert "web.memory.poison" in ids
