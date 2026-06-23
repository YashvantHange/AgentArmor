"""Memory agent multi-turn generation tests."""

import pytest

from agentarmor.core.config import AppConfig, RedTeamBudgetConfig, RedTeamConfig, RedTeamMultiAgentConfig
from agentarmor.redteam.agents.attack.memory_agent import MemoryAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, TargetProfile


@pytest.fixture
def offline_config():
    cfg = AppConfig(
        redteam=RedTeamConfig(
            multi_agent=RedTeamMultiAgentConfig(),
            budget=RedTeamBudgetConfig(),
        )
    )
    cfg.detection.analysis_mode = "offline"
    return cfg


@pytest.mark.asyncio
async def test_memory_agent_multi_turn(offline_config):
    agent = MemoryAgent()
    budget = BudgetGovernor(offline_config.redteam.budget)
    plan = AttackPlan(path_id="memory_chain", next_node="memory_poison", strategy="direct")
    attack = await agent.generate(
        offline_config,
        budget,
        TargetProfile(memory=True),
        plan,
    )
    assert attack.multi_turn is not None
    assert len(attack.multi_turn) >= 2
    assert "LLM01" in attack.owasp or "LLM04" in attack.owasp


@pytest.mark.asyncio
async def test_memory_agent_applies_mutation_on_retry(offline_config):
    agent = MemoryAgent()
    budget = BudgetGovernor(offline_config.redteam.budget)
    plan = AttackPlan(path_id="memory_chain", next_node="memory_poison", strategy="mutation_retry")
    attack = await agent.generate(
        offline_config,
        budget,
        TargetProfile(memory=True),
        plan,
    )
    assert attack.mutations_applied
