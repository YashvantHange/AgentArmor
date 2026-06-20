"""LiteLLM completion wrapper for cloud provider scanning."""

from __future__ import annotations

import time
from typing import Any

# Default model per provider shorthand (LiteLLM model strings)
PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-3.5-turbo",
    "anthropic": "anthropic/claude-3-haiku-20240307",
    "gemini": "gemini/gemini-pro",
    "mistral": "mistral/mistral-small-latest",
    "bedrock": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    "azure": "azure/gpt-35-turbo",
    "groq": "groq/llama-3.1-8b-instant",
    "together": "together_ai/meta-llama/Llama-3-8b-chat-hf",
    "openrouter": "openrouter/openai/gpt-3.5-turbo",
}

SUPPORTED_PROVIDERS = frozenset(PROVIDER_DEFAULTS)


def resolve_model(provider: str, model: str | None) -> str:
    """Map provider shorthand + optional model override to a LiteLLM model id."""
    if model:
        if "/" in model or model.startswith("gpt-"):
            return model
        return f"{provider}/{model}" if provider in SUPPORTED_PROVIDERS else model
    return PROVIDER_DEFAULTS.get(provider, provider)


async def completion(
    provider: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
) -> tuple[str, dict[str, Any], float]:
    """Run LiteLLM acompletion; returns (content, raw_dict, latency_ms)."""
    import litellm

    model_id = resolve_model(provider, model)
    start = time.perf_counter()
    response = await litellm.acompletion(
        model=model_id,
        messages=messages,
        temperature=temperature,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    raw = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    content = ""
    choices = raw.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content", "") or ""
    return content, raw, latency_ms
