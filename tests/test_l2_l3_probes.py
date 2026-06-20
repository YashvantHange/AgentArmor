"""L2/L3 probe tests."""

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Target
from agentarmor.orchestrator.probes.l2_mutation import get_l2_probes
from agentarmor.orchestrator.probes.l3_multiturn import MAX_TURNS, get_l3_probes


def test_l2_probe_count():
    probes = get_l2_probes()
    assert len(probes) == 5
    ids = {p.id for p in probes}
    assert "l2.encoding-base64" in ids
    assert "l2.context-split" in ids


def test_l2_build_request():
    cfg = AppConfig(target=Target(model="gpt-3.5-turbo"))
    probe = get_l2_probes()[0]
    req = probe.build_request(cfg)
    assert req.messages[0]["content"]
    assert "base64" in req.messages[0]["content"].lower() or "Decode" in req.messages[0]["content"]


def test_l3_probe_count():
    probes = get_l3_probes()
    assert len(probes) == 4


def test_l3_turn_cap():
    cfg = AppConfig(target=Target(model="gpt-3.5-turbo"))
    for probe in get_l3_probes():
        steps = probe.get_conversation_steps(cfg)
        assert len(steps) <= MAX_TURNS
        assert len(steps) >= 2
