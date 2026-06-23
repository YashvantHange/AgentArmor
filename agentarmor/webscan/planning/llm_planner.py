"""LLM-powered attack probe generation for multi-agentic web scans."""

from __future__ import annotations

import json
import re
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.webscan.models import AgentRiskProfile, CapabilityMap, WebProbeDef
from agentarmor.webscan.planning.prompts import ATTACK_PLANNER_SYSTEM


def _parse_planner_json(raw: str) -> list[dict[str, Any]]:
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
    if isinstance(data, list):
        probes = data
    elif isinstance(data, dict):
        probes = data.get("probes", [])
    else:
        return []
    return [p for p in probes if isinstance(p, dict)]


def _sanitize_probe(entry: dict[str, Any], index: int) -> WebProbeDef | None:
    prompt = str(entry.get("prompt", "")).strip()
    if not prompt or len(prompt) > 500:
        return None
    if re.search(r"(cookie|bearer\s|session[_-]?id|storage.?state)", prompt, re.I):
        return None
    raw_id = str(entry.get("id", f"web.llm.custom-{index}")).strip()
    if not raw_id.startswith("web.llm."):
        raw_id = f"web.llm.custom-{index}"
    owasp = entry.get("owasp") or ["LLM01"]
    if isinstance(owasp, str):
        owasp = [owasp]
    owasp = [str(o) for o in owasp if str(o).startswith("LLM")][:3]
    if not owasp:
        owasp = ["LLM01"]
    name = str(entry.get("name", "LLM Custom Probe")).strip()[:120] or "LLM Custom Probe"
    return WebProbeDef(id=raw_id, name=name, owasp=owasp, prompt=prompt)


async def generate_llm_probes(
    capability_map: CapabilityMap,
    agent_risk: AgentRiskProfile | None,
    config: AppConfig,
    *,
    max_probes: int = 8,
) -> list[WebProbeDef]:
    """Generate custom probes via cloud LLM; returns empty list when cloud is unavailable."""
    agentic = config.detection.agentic
    if config.detection.analysis_mode != "cloud" or not agentic.enabled:
        return []
    api_key = agentic.api_key or ""
    if not api_key:
        return []

    cap_summary = {
        "framework": capability_map.framework,
        "rag": capability_map.rag,
        "memory": capability_map.memory,
        "mcp": capability_map.mcp,
        "a2a": capability_map.a2a,
        "tools": capability_map.tools[:8],
        "risk_score": capability_map.risk_score,
        "risk_reasons": capability_map.risk_reasons[:5],
    }
    if agent_risk:
        cap_summary["agent_risk_score"] = agent_risk.risk_score
        cap_summary["external_actions"] = agent_risk.external_actions

    user = (
        f"capability_map: {json.dumps(cap_summary)}\n"
        f"Generate up to {max_probes} targeted probes for this chatbot."
    )

    import litellm

    model = agentic.model
    if "/" not in model:
        model = f"{agentic.provider}/{model}"

    try:
        completion = await litellm.acompletion(
            model=model,
            api_key=api_key or None,
            messages=[
                {"role": "system", "content": ATTACK_PLANNER_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        content = (completion.choices[0].message.content or "").strip()
    except Exception:
        return []

    probes: list[WebProbeDef] = []
    seen: set[str] = set()
    for idx, entry in enumerate(_parse_planner_json(content)):
        probe = _sanitize_probe(entry, idx + 1)
        if not probe or probe.id in seen:
            continue
        seen.add(probe.id)
        probes.append(probe)
        if len(probes) >= max_probes:
            break
    return probes
