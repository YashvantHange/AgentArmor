"""Scan plan preview — estimate probes, duration, and cost before execution."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.orchestrator.planning.owasp_planner import build_probe_plan, plan_probes_for_config
from agentarmor.orchestrator.runner import _collect_all_engine_probes


async def preview_scan_plan(config: AppConfig) -> dict:
    from agentarmor.orchestrator.planning.adapters import plan_for_target

    plan = await plan_for_target(config)

    est_tokens = plan.estimated_probes * 500
    est_cost_usd = round(est_tokens * 0.000002, 4)

    agentic = config.detection.agentic
    over_budget = (
        est_tokens > agentic.max_tokens_per_scan
        or est_cost_usd > agentic.max_cost_usd_per_scan
    )

    rem_by_layer: dict[str, int] = {}
    for p in plan.probes:
        rem_by_layer[p.layer] = rem_by_layer.get(p.layer, 0) + 1

    return {
        "planner_version": plan.planner_version,
        "estimated_probes": plan.estimated_probes,
        "estimated_duration_min": plan.estimated_duration_min,
        "estimated_tokens": est_tokens,
        "estimated_cost_usd": est_cost_usd,
        "over_budget": over_budget,
        "budget_limits": {
            "max_tokens": agentic.max_tokens_per_scan,
            "max_cost_usd": agentic.max_cost_usd_per_scan,
        },
        "total_work_units": plan.total_work_units,
        "probes_by_owasp": plan.probes_by_owasp,
        "remaining_by_layer": rem_by_layer,
        "skipped_probes": [{"id": s.id, "reason": s.reason} for s in plan.skipped[:50]],
        "selected_probe_ids": plan.selected_ids,
        "capabilities": plan.capabilities.to_dict(),
    }


def enforce_plan_budget(config: AppConfig, preview: dict) -> None:
    """Raise if plan exceeds configured token/cost limits."""
    if preview.get("over_budget"):
        limits = preview.get("budget_limits", {})
        raise ValueError(
            f"Scan plan exceeds budget: ~{preview.get('estimated_tokens')} tokens "
            f"(max {limits.get('max_tokens')}) or "
            f"~${preview.get('estimated_cost_usd')} (max ${limits.get('max_cost_usd')}). "
            "Reduce scan_depth, owasp_ids, or raise limits in settings."
        )
