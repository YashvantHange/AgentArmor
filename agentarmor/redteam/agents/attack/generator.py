"""Delegate attack generation to the agent registry."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.registry import resolve_agent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile


async def generate_attack(
    config: AppConfig,
    budget: BudgetGovernor,
    profile: TargetProfile,
    plan: AttackPlan,
    *,
    last_response: str = "",
) -> AttackPrompt:
    agent = resolve_agent(plan.next_node)
    return await agent.generate(
        config,
        budget,
        profile,
        plan,
        last_response=last_response,
    )


def judge_rubric_for_node(node_id: str) -> str:
    agent = resolve_agent(node_id)
    return agent.judge_rubric_for(node_id)
