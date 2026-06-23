"""Execute red-team attacks against API, module, or web targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResult
from agentarmor.engines.router import send_probe
from agentarmor.modules.agent.runner import run_agent_probe
from agentarmor.modules.mcp.runner import run_mcp_probe
from agentarmor.modules.rag.runner import run_rag_probe
from agentarmor.modules.router import is_module_target
from agentarmor.redteam.schemas import AttackPrompt
from agentarmor.webscan.models import WebProbeDef, WidgetCandidate
from agentarmor.webscan.probes.executor import execute_multi_turn_probe, execute_probe


@dataclass
class WebExecutionContext:
    page: Any
    widget: WidgetCandidate
    stable_ms: int = 1500
    max_wait_ms: int = 45000


def attack_to_web_probe(attack: AttackPrompt) -> WebProbeDef:
    turns = 1
    follow_up: str | None = None
    if attack.multi_turn and len(attack.multi_turn) >= 2:
        turns = len(attack.multi_turn)
        follow_up = attack.multi_turn[1] if len(attack.multi_turn) > 1 else None
    return WebProbeDef(
        id=attack.probe_id,
        name=attack.name,
        owasp=attack.owasp,
        prompt=attack.prompt,
        turns=turns,
        follow_up_prompt=follow_up,
    )


async def execute_attack(
    config: AppConfig,
    attack: AttackPrompt,
    *,
    web_ctx: WebExecutionContext | None = None,
) -> tuple[ProbeResult, str, list[dict[str, str]]]:
    """Dispatch attack to the appropriate target backend."""
    if web_ctx is not None:
        return await _execute_web(config, attack, web_ctx)

    if is_module_target(config):
        return await _execute_module(config, attack)

    return await _execute_api(config, attack)


async def _execute_api(
    config: AppConfig,
    attack: AttackPrompt,
) -> tuple[ProbeResult, str, list[dict[str, str]]]:
    model = config.target.model or "gpt-3.5-turbo"
    if attack.multi_turn:
        last: ProbeResult | None = None
        messages: list[dict[str, str]] = []
        for turn in attack.multi_turn:
            messages.append({"role": "user", "content": turn})
            request = ProbeRequest(messages=list(messages), model=model)
            last = await send_probe(
                config, attack.probe_id, attack.name, attack.owasp, request
            )
            if last.response.content:
                messages.append({"role": "assistant", "content": last.response.content})
        assert last is not None
        prompt_text = attack.multi_turn[-1]
        return last, prompt_text, messages

    request = ProbeRequest(
        messages=[{"role": "user", "content": attack.prompt}],
        model=model,
    )
    result = await send_probe(
        config, attack.probe_id, attack.name, attack.owasp, request
    )
    return result, attack.prompt, request.messages


async def _execute_module(
    config: AppConfig,
    attack: AttackPrompt,
) -> tuple[ProbeResult, str, list[dict[str, str]]]:
    from agentarmor.modules.agent.runner import list_agent_probes
    from agentarmor.modules.mcp.runner import list_mcp_probes
    from agentarmor.modules.rag.runner import list_rag_probes

    target_type = config.target.type.value
    probes = {
        "agent": list_agent_probes,
        "mcp": list_mcp_probes,
        "rag": list_rag_probes,
    }.get(target_type, list_agent_probes)()

    module_probe = probes[0] if probes else None
    if module_probe is None:
        return await _execute_api(config, attack)

    if target_type == "agent":
        result = await run_agent_probe(config, module_probe)
    elif target_type == "mcp":
        result = await run_mcp_probe(config, module_probe)
    else:
        result = await run_rag_probe(config, module_probe)

    prompt = attack.prompt
    if result.request.messages:
        result.request.messages[-1]["content"] = attack.prompt
        prompt = attack.prompt
    return result, prompt, result.request.messages


async def _execute_web(
    config: AppConfig,
    attack: AttackPrompt,
    web_ctx: WebExecutionContext,
) -> tuple[ProbeResult, str, list[dict[str, str]]]:
    from agentarmor.core.models import ProbeResponse

    probe = attack_to_web_probe(attack)
    skip_reload = probe.turns >= 2 and probe.follow_up_prompt
    try:
        if skip_reload:
            stable = await execute_multi_turn_probe(
                web_ctx.page,
                web_ctx.widget,
                probe,
                stable_ms=web_ctx.stable_ms,
                max_wait_ms=web_ctx.max_wait_ms,
            )
        else:
            stable = await execute_probe(
                web_ctx.page,
                web_ctx.widget,
                probe,
                stable_ms=web_ctx.stable_ms,
                max_wait_ms=web_ctx.max_wait_ms,
            )
        response_text = stable.text
        error = None
    except Exception as exc:
        response_text = ""
        error = str(exc)
        stable = None

    result = ProbeResult(
        probe_id=attack.probe_id,
        probe_name=attack.name,
        owasp=attack.owasp,
        request=ProbeRequest(messages=[{"role": "user", "content": attack.prompt}]),
        response=ProbeResponse(content=response_text, status_code=200 if not error else 0),
        error=error,
        metadata={"webscan": True, "redteam": True},
    )
    if stable is not None:
        result.metadata["stable"] = stable.model_dump()
    return result, attack.prompt, [{"role": "user", "content": attack.prompt}]
