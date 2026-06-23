"""LLM01-LLM10 agent generation tests (offline fallback)."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.registry import all_agents
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, TargetProfile

_NODE_BY_AGENT = {
    "llm01": "prompt_injection",
    "llm02": "sensitive_disclosure",
    "llm03": "supply_chain_abuse",
    "llm04": "data_poisoning",
    "llm05": "improper_output",
    "llm06": "email_exfil",
    "llm07": "system_prompt_leak",
    "llm08": "rag_override",
    "llm09": "overreliance",
    "llm10": "model_theft",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id,node_id", list(_NODE_BY_AGENT.items()))
async def test_owasp_agent_offline_generate(agent_id, node_id):
    cfg = AppConfig()
    cfg.detection.analysis_mode = "offline"
    agent = all_agents()[agent_id]
    budget = BudgetGovernor(cfg.redteam.budget)
    plan = AttackPlan(path_id="test", next_node=node_id, strategy="direct")
    attack = await agent.generate(cfg, budget, TargetProfile(), plan)
    assert attack.prompt
    assert len(attack.prompt) <= 500
    assert attack.probe_id.startswith("redteam.")
    assert attack.owasp
