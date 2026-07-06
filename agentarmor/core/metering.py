"""Provider-neutral LLM usage metering.

Lets lower-level packages (detection, webscan) report token/cost usage to a budget
tracker without importing the red-team budget package. Any object exposing a
``record_usage`` method with the keyword signature below satisfies ``UsageMeter``
(``redteam.budget.governor.BudgetGovernor`` does).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class UsageMeter(Protocol):
    def record_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None: ...


def extract_litellm_usage(completion: Any) -> tuple[int, int, float | None]:
    """Pull (input_tokens, output_tokens, response_cost) from a LiteLLM completion."""
    usage = getattr(completion, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    cost: float | None = None
    hidden = getattr(completion, "_hidden_params", {}) or {}
    if isinstance(hidden, dict):
        raw = hidden.get("response_cost")
        cost = float(raw) if raw else None
    return input_tokens, output_tokens, cost


def record_completion_usage(
    meter: UsageMeter | None, completion: Any, model: str
) -> None:
    """Record a LiteLLM completion's usage against ``meter`` (no-op if meter is None)."""
    if meter is None:
        return
    input_tokens, output_tokens, cost = extract_litellm_usage(completion)
    meter.record_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        litellm_cost=cost,
    )
