"""Target-specific planner adapters over shared OWASP core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentarmor.core.config import AppConfig
from agentarmor.core.models import TargetType
from agentarmor.orchestrator.planning.capabilities import detect_capabilities_async
from agentarmor.orchestrator.planning.owasp_planner import ProbePlanResult, build_probe_plan, plan_probes_for_config

if TYPE_CHECKING:
    from agentarmor.orchestrator.runner import RunnableProbe


async def plan_endpoint_probes(config: AppConfig) -> ProbePlanResult:
    from agentarmor.orchestrator.runner import _collect_all_engine_probes

    all_probes = await _collect_all_engine_probes(config)
    return await plan_probes_for_config(config, all_probes)


def _module_to_runnable(probes: list, layer: str) -> list:
    from agentarmor.orchestrator.runner import RunnableProbe

    out: list[RunnableProbe] = []
    for p in probes:
        out.append(
            RunnableProbe(
                id=p.id,
                name=p.name,
                owasp=list(p.owasp),
                layer=layer,
                module_kind=layer,
                module_probe=p,
            )
        )
    return out


async def plan_agent_probes(config: AppConfig) -> ProbePlanResult:
    from agentarmor.modules.agent.runner import list_agent_probes

    runnable = _module_to_runnable(list_agent_probes(), "agent")
    caps = await detect_capabilities_async(config)
    return build_probe_plan(
        runnable,
        owasp_ids=config.planner.owasp_ids,
        scan_depth=config.planner.scan_depth,
        owasp_depths=config.planner.owasp_depths,
        capabilities=caps,
    )


async def plan_mcp_probes(config: AppConfig) -> ProbePlanResult:
    from agentarmor.modules.mcp.runner import list_mcp_probes

    runnable = _module_to_runnable(list_mcp_probes(), "mcp")
    caps = await detect_capabilities_async(config)
    return build_probe_plan(
        runnable,
        owasp_ids=config.planner.owasp_ids,
        scan_depth=config.planner.scan_depth,
        owasp_depths=config.planner.owasp_depths,
        capabilities=caps,
    )


async def plan_rag_probes(config: AppConfig) -> ProbePlanResult:
    from agentarmor.modules.rag.runner import list_rag_probes

    runnable = _module_to_runnable(list_rag_probes(), "rag")
    caps = await detect_capabilities_async(config)
    return build_probe_plan(
        runnable,
        owasp_ids=config.planner.owasp_ids,
        scan_depth=config.planner.scan_depth,
        owasp_depths=config.planner.owasp_depths,
        capabilities=caps,
    )


async def plan_web_probes_from_catalog(config: AppConfig, web_probe_defs: list) -> ProbePlanResult:
    from agentarmor.orchestrator.runner import RunnableProbe

    runnable: list[RunnableProbe] = []
    for wp in web_probe_defs:
        layer = "L2" if getattr(wp, "turns", 1) > 1 else "L1"
        runnable.append(
            RunnableProbe(
                id=wp.id,
                name=wp.name,
                owasp=list(wp.owasp),
                layer=layer,
            )
        )
    caps = await detect_capabilities_async(config)
    return build_probe_plan(
        runnable,
        owasp_ids=config.planner.owasp_ids,
        scan_depth=config.planner.scan_depth,
        owasp_depths=config.planner.owasp_depths,
        capabilities=caps,
    )


async def plan_for_target(config: AppConfig, web_probe_defs: list | None = None) -> ProbePlanResult:
    t = config.target.type
    if t == TargetType.AGENT:
        return await plan_agent_probes(config)
    if t == TargetType.MCP:
        return await plan_mcp_probes(config)
    if t == TargetType.RAG:
        return await plan_rag_probes(config)
    if web_probe_defs is not None:
        return await plan_web_probes_from_catalog(config, web_probe_defs)
    return await plan_endpoint_probes(config)
