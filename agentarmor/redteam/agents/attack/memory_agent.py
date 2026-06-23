"""Memory attack agent — multi-turn poison, store, recall."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.attack._llm_mixin import generate_from_skill, judge_rubric_for_node
from agentarmor.redteam.agents.base import BaseAttackAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile


class MemoryAgent(BaseAttackAgent):
    agent_id = "memory"
    owasp = ["LLM01", "LLM04", "LLM06"]

    async def generate(
        self,
        config: AppConfig,
        budget: BudgetGovernor,
        profile: TargetProfile,
        plan: AttackPlan,
        *,
        last_response: str = "",
    ) -> AttackPrompt:
        attack = await generate_from_skill(
            "memory",
            config,
            budget,
            profile,
            plan,
            last_response=last_response,
        )
        if not attack.multi_turn:
            from agentarmor.redteam.skills.loader import skill_for_node

            skill = skill_for_node(plan.next_node, "memory")
            if skill and skill.multi_turn:
                attack = attack.model_copy(update={"multi_turn": list(skill.multi_turn)})
        return attack

    def judge_rubric_for(self, node_id: str) -> str:
        return judge_rubric_for_node("memory", node_id)
