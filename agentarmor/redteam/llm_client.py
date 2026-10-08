"""LiteLLM wrapper with budget accounting, timeout, and bounded retries."""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any
from weakref import WeakKeyDictionary

from agentarmor.core.config import AppConfig
from agentarmor.detection.agentic.preflight import is_auth_error
from agentarmor.redteam.budget.governor import BudgetGovernor

# Transient conditions worth another attempt. 5xx is listed explicitly rather
# than matched as a range so a 4xx is never retried by accident.
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
_RETRYABLE_TEXT = (
    "rate limit",
    "ratelimit",
    "too many requests",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "overloaded",
    "connection reset",
    "connection refused",
    "connection error",
    "remote end closed",
    "server disconnected",
)
# Permanent conditions: retrying burns budget and cannot succeed.
_FATAL_TEXT = (
    "context length",
    "context_length",
    "maximum context",
    "too many tokens",
    "invalid request",
    "invalid_request",
    "model not found",
    "does not exist",
    "unsupported",
    "content policy",
    "content_policy",
    "safety filter",
)

# One semaphore per event loop. asyncio primitives bind to the loop that created
# them, and the CLI runs asyncio.run per command while pytest builds a loop per
# test, so a module-level semaphore would raise on the second loop. Held weakly
# so entries die with the loop.
_SEMAPHORES: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    WeakKeyDictionary()
)


def _status_of(exc: Exception) -> int | None:
    for attr in ("status_code", "code", "http_status"):
        value = getattr(exc, attr, None)
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return None


def is_retryable(exc: Exception) -> bool:
    """Classify an exception explicitly. Never retry what cannot succeed."""
    if isinstance(exc, asyncio.TimeoutError):
        return True
    # An auth failure is the one error the caller most needs to see immediately.
    if is_auth_error(exc):
        return False
    status = _status_of(exc)
    if status is not None:
        return status in _RETRYABLE_STATUS
    text = str(exc).lower()
    if any(token in text for token in _FATAL_TEXT):
        return False
    return any(token in text for token in _RETRYABLE_TEXT)


def _semaphore(limit: int) -> asyncio.Semaphore:
    """Per-loop concurrency cap. Called only from async code, so a loop exists."""
    loop = asyncio.get_running_loop()
    sem = _SEMAPHORES.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(max(1, limit))
        _SEMAPHORES[loop] = sem
    return sem


def _estimate_tokens(system: str, user: str) -> int:
    """Rough prompt-size estimate, used to charge attempts that returned no usage."""
    return max(1, (len(system) + len(user)) // 4)


async def completion_json(
    config: AppConfig,
    budget: BudgetGovernor,
    *,
    system: str,
    user: str,
    agent_name: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Call LiteLLM and return parsed JSON dict + trace metadata.

    ``timeout_s`` defaults to ``detection.agentic.timeout_s``, which already
    existed and was simply never applied here, so a hung provider call could
    stall a scan indefinitely. ``max_retries`` defaults to
    ``swarm.llm_max_retries``.

    A timed-out attempt is charged an estimated cost, because the provider may
    have completed and billed the call while we never saw the usage object;
    leaving it unrecorded would let one logical agent make several billable calls
    while the ledger showed none. Rejections (rate limit, auth, invalid request)
    did no inference and are not charged.
    """
    agentic = config.detection.agentic
    trace: dict[str, Any] = {"agent": agent_name, "model": agentic.model, "attempts": 0}
    if not budget.allow_continue():
        trace["error"] = budget.state.stop_reason or "budget exhausted"
        return None, trace

    import litellm

    model = agentic.model
    if "/" not in model:
        model = f"{agentic.provider}/{model}"

    effective_timeout = timeout_s if timeout_s is not None else agentic.timeout_s
    retries = max_retries if max_retries is not None else config.swarm.llm_max_retries
    retries = max(0, retries)
    sem = _semaphore(config.swarm.llm_max_concurrent)

    start = time.perf_counter()
    last_error: str = ""

    for attempt in range(retries + 1):
        trace["attempts"] = attempt + 1
        if attempt and not budget.allow_continue():
            last_error = budget.state.stop_reason or "budget exhausted"
            break
        try:
            async with sem:
                completion = await asyncio.wait_for(
                    litellm.acompletion(
                        model=model,
                        api_key=agentic.api_key or None,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=temperature if temperature is not None else agentic.temperature,
                        max_tokens=max_tokens or agentic.max_output_tokens,
                    ),
                    timeout=effective_timeout,
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
            return _parse_json(content), trace

        except Exception as exc:  # noqa: BLE001 - classified below
            timed_out = isinstance(exc, asyncio.TimeoutError)
            last_error = "timeout" if timed_out else str(exc)
            if timed_out:
                # A timeout means the provider may have completed and billed the
                # call while we never saw the usage object. A rejection (429,
                # auth, invalid request) did no inference, so charging for it
                # would overstate spend. Only the ambiguous case is charged.
                budget.record_usage(
                    input_tokens=_estimate_tokens(system, user),
                    output_tokens=0,
                    model=agentic.model,
                )
            if attempt >= retries or not is_retryable(exc):
                break
            delay = 0.5 * (2**attempt) + random.uniform(0, 0.25)
            await asyncio.sleep(delay)

    trace["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    trace["error"] = last_error
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
