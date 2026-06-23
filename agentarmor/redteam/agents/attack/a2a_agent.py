"""A2A handoff and privilege-ride attack agent."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.attack._llm_mixin import generate_from_skill, judge_rubric_for_node
from agentarmor.redteam.agents.base import BaseAttackAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile


class A2AAgent(BaseAttackAgent):
    agent_id = "a2a"
    owasp = ["LLM06", "LLM02"]

    async def generate(
        self,
        config: AppConfig,
        budget: BudgetGovernor,
        profile: TargetProfile,
        plan: AttackPlan,
        *,
        last_response: str = "",
    ) -> AttackPrompt:
        return await generate_from_skill(
            "a2a",
            config,
            budget,
            profile,
            plan,
            last_response=last_response,
        )

    def judge_rubric_for(self, node_id: str) -> str:
        return judge_rubric_for_node("a2a", node_id)
