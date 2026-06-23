"""Agent registry resolution tests."""

from agentarmor.redteam.agents.registry import list_agent_ids, resolve_agent


def test_all_owasp_agents_registered():
    ids = set(list_agent_ids())
    for n in range(1, 11):
        assert f"llm{n:02d}" in ids


def test_resolve_memory_nodes():
    agent = resolve_agent("memory_poison")
    assert agent.agent_id == "memory"


def test_resolve_mcp_nodes():
    assert resolve_agent("mcp_cross_server").agent_id == "mcp"


def test_resolve_a2a_nodes():
    assert resolve_agent("a2a_handoff").agent_id == "a2a"


def test_resolve_llm_baselines():
    assert resolve_agent("prompt_injection").agent_id == "llm01"
    assert resolve_agent("model_theft").agent_id == "llm10"
