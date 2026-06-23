"""Attack graph builder tests."""

from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import TargetProfile


def test_memory_path_ranked_first():
    profile = TargetProfile(memory=True, rag=True, email_tool=True)
    paths = build_attack_graph(profile)
    assert paths[0].path_id == "memory_chain"
    assert any(n.node_id == "memory_poison" for n in paths[0].nodes)


def test_a2a_path_when_detected():
    profile = TargetProfile(a2a=True)
    paths = build_attack_graph(profile)
    ids = {p.path_id for p in paths}
    assert "a2a_handoff" in ids


def test_baseline_paths_always_present():
    profile = TargetProfile()
    paths = build_attack_graph(profile)
    ids = {p.path_id for p in paths}
    assert "prompt_injection" in ids
    assert "system_prompt_leak" in ids


def test_mcp_cross_server_path():
    profile = TargetProfile(mcp=True)
    paths = build_attack_graph(profile)
    mcp = next(p for p in paths if p.path_id == "mcp_abuse")
    assert any(n.node_id == "mcp_cross_server" for n in mcp.nodes)
