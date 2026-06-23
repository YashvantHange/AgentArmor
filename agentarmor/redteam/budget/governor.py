"""Token and cost budget tracking for red team LLM calls."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentarmor.core.config import RedTeamBudgetConfig
from agentarmor.redteam.schemas import BudgetState

# Approximate USD per 1M tokens (input+output blended) when litellm cost unavailable
_FALLBACK_COST_PER_1M: dict[str, float] = {
    "gpt-4o": 5.0,
    "gpt-4o-mini": 0.3,
    "claude-3-5-sonnet": 3.0,
    "claude-3-haiku": 0.25,
    "gemini": 0.5,
}


@dataclass
class BudgetGovernor:
    config: RedTeamBudgetConfig
    state: BudgetState = field(default_factory=BudgetState)

    def allow_continue(self) -> bool:
        if self.state.stopped:
            return False
        if self.state.tokens_used >= self.config.max_tokens:
            self._stop("max_tokens exceeded")
            return False
        if self.state.cost_usd >= self.config.max_cost_usd:
            self._stop("max_cost_usd exceeded")
            return False
        return True

    def record_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None:
        total = input_tokens + output_tokens
        self.state.tokens_used += total
        self.state.calls += 1
        if litellm_cost is not None:
            self.state.cost_usd += litellm_cost
        else:
            self.state.cost_usd += _estimate_cost(model, total)
        warn_pct = self.config.warn_at_pct / 100.0
        if self.state.tokens_used >= self.config.max_tokens * warn_pct:
            self.state.degraded = True
        if self.state.cost_usd >= self.config.max_cost_usd * warn_pct:
            self.state.degraded = True
        if not self.allow_continue():
            pass

    def should_degrade(self) -> bool:
        return self.state.degraded and not self.state.stopped

    def _stop(self, reason: str) -> None:
        self.state.stopped = True
        self.state.stop_reason = reason


def _estimate_cost(model: str, tokens: int) -> float:
    model_lower = model.lower()
    rate = 1.0
    for key, val in _FALLBACK_COST_PER_1M.items():
        if key in model_lower:
            rate = val
            break
    return (tokens / 1_000_000) * rate
