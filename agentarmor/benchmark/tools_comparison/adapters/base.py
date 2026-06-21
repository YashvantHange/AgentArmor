"""Tool adapter base for benchmark comparison."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentarmor.benchmark.tools_comparison.corpus import ComparisonScenario
from agentarmor.benchmark.tools_comparison.models import ToolScore
from agentarmor.core.config import AppConfig


class ToolAdapter(ABC):
    name: str

    @abstractmethod
    async def evaluate(self, scenarios: list[ComparisonScenario], config: AppConfig) -> ToolScore:
        ...
