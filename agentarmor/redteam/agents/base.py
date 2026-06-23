"""Base class for red-team attack agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentarmor.core.config import AppConfig
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile


class BaseAttackAgent(ABC):
    agent_id: str
    owasp: list[str]

    @abstractmethod
    async def generate(
        self,
        config: AppConfig,
        budget: BudgetGovernor,
        profile: TargetProfile,
        plan: AttackPlan,
        *,
        last_response: str = "",
    ) -> AttackPrompt:
        ...

    @abstractmethod
    def judge_rubric_for(self, node_id: str) -> str:
        ...
