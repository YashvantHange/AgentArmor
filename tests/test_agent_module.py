"""Agent module tests."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Target, TargetType
from agentarmor.modules.agent.probes import get_agent_probes
from agentarmor.modules.agent.runner import run_agent_probe


def test_agent_probe_count():
    assert len(get_agent_probes()) == 5
    assert all("LLM06" in p.owasp for p in get_agent_probes())


@pytest.mark.asyncio
async def test_agent_tool_abuse_finding():
    cfg = AppConfig(target=Target(type=TargetType.AGENT, agent_framework="crewai"))
    probe = get_agent_probes()[0]
    result = await run_agent_probe(cfg, probe)
    assert result.metadata.get("triggered") is True
    assert "file_delete" in result.response.content or "admin_shell" in str(
        result.response.raw.get("tool_calls", [])
    )


@pytest.mark.asyncio
async def test_langgraph_adapter():
    cfg = AppConfig(target=Target(type=TargetType.AGENT, agent_framework="langgraph"))
    probe = next(p for p in get_agent_probes() if p.id == "agent.workflow-hijacking")
    result = await run_agent_probe(cfg, probe)
    assert result.metadata.get("triggered") is True
