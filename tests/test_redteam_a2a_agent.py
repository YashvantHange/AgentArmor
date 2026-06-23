"""A2A agent tests."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.attack.a2a_agent import A2AAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, TargetProfile


@pytest.mark.asyncio
async def test_a2a_handoff_prompt():
    cfg = AppConfig()
    cfg.detection.analysis_mode = "offline"
    agent = A2AAgent()
    budget = BudgetGovernor(cfg.redteam.budget)
    plan = AttackPlan(path_id="a2a_handoff", next_node="a2a_handoff", strategy="direct")
    attack = await agent.generate(cfg, budget, TargetProfile(a2a=True), plan)
    assert "admin" in attack.prompt.lower() or "agent" in attack.prompt.lower()
    assert "LLM06" in attack.owasp


@pytest.mark.asyncio
async def test_a2a_judge_rubric():
    agent = A2AAgent()
    rubric = agent.judge_rubric_for("a2a_privilege_ride")
    assert "handoff" in rubric.lower() or "agent" in rubric.lower() or "credential" in rubric.lower()
