"""MCP enumeration and cross-server attack agent."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.attack._llm_mixin import generate_from_skill, judge_rubric_for_node
from agentarmor.redteam.agents.base import BaseAttackAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile


class MCPAgent(BaseAttackAgent):
    agent_id = "mcp"
    owasp = ["LLM06"]

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
            "mcp",
            config,
            budget,
            profile,
            plan,
            last_response=last_response,
        )

    def judge_rubric_for(self, node_id: str) -> str:
        return judge_rubric_for_node("mcp", node_id)
