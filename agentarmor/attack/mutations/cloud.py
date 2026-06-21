"""Cloud LLM mutation agent — novel attack wrappers in Cloud Enhanced mode."""

from __future__ import annotations

import json
import time
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.detection.agentic.prompts import MUTATION_AGENT_SYSTEM


async def generate_cloud_mutations(
    *,
    goal_id: str,
    goal_name: str,
    seed: str,
    config: AppConfig,
    count: int = 10,
) -> list[tuple[str, str]]:
    """Return (technique, prompt) pairs from LLM mutation agent. Empty if cloud unavailable."""
    agentic = config.detection.agentic
    if config.detection.analysis_mode != "cloud" or not agentic.enabled:
        return []
    api_key = agentic.api_key or ""
    if not api_key:
        return []

    user = (
        f"attack_goal: {goal_name} ({goal_id})\n"
        f"seed_prompt: {seed[:1200]}\n"
        f"count: {min(count, 15)}\n"
        "Generate novel mutation wrappers for the seed that pursue the attack goal."
    )

    import litellm

    start = time.perf_counter()
    try:
        model = agentic.model
        if "/" not in model:
            model = f"{agentic.provider}/{model}"
        completion = await litellm.acompletion(
            model=model,
            api_key=api_key or None,
            messages=[
                {"role": "system", "content": MUTATION_AGENT_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        content = (completion.choices[0].message.content or "").strip()
        parsed = _parse_mutations_json(content)
        results: list[tuple[str, str]] = []
        for item in parsed[:count]:
            technique = str(item.get("technique", "cloud_llm")).strip() or "cloud_llm"
            prompt = str(item.get("prompt", "")).strip()
            if prompt and prompt != seed:
                results.append((technique, prompt))
        _ = time.perf_counter() - start
        return results
    except Exception:
        return []


def _parse_mutations_json(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        mutations = data.get("mutations")
        if isinstance(mutations, list):
            return [m for m in mutations if isinstance(m, dict)]
    return []
