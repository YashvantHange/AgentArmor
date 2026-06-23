"""LiteLLM wrapper with budget accounting."""

from __future__ import annotations

import json
import time
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.redteam.budget.governor import BudgetGovernor


async def completion_json(
    config: AppConfig,
    budget: BudgetGovernor,
    *,
    system: str,
    user: str,
    agent_name: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Call LiteLLM and return parsed JSON dict + trace metadata."""
    agentic = config.detection.agentic
    trace: dict[str, Any] = {"agent": agent_name, "model": agentic.model}
    if not budget.allow_continue():
        trace["error"] = budget.state.stop_reason or "budget exhausted"
        return None, trace

    import litellm

    model = agentic.model
    if "/" not in model:
        model = f"{agentic.provider}/{model}"
    start = time.perf_counter()
    try:
        completion = await litellm.acompletion(
            model=model,
            api_key=agentic.api_key or None,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature if temperature is not None else agentic.temperature,
            max_tokens=max_tokens or agentic.max_output_tokens,
        )
        content = (completion.choices[0].message.content or "").strip()
        usage = getattr(completion, "usage", None)
        input_t = getattr(usage, "prompt_tokens", 0) or 0
        output_t = getattr(usage, "completion_tokens", 0) or 0
        cost = None
        hidden = getattr(completion, "_hidden_params", {}) or {}
        if isinstance(hidden, dict):
            cost = hidden.get("response_cost")
        budget.record_usage(
            input_tokens=int(input_t),
            output_tokens=int(output_t),
            model=agentic.model,
            litellm_cost=float(cost) if cost else None,
        )
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        trace["tokens"] = int(input_t) + int(output_t)
        parsed = _parse_json(content)
        return parsed, trace
    except Exception as exc:
        trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        trace["error"] = str(exc)
        return None, trace


def _parse_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
