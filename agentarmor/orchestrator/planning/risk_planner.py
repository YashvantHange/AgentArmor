"""Risk-based probe ordering and adaptive depth expansion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentarmor.orchestrator.planning.owasp_planner import build_probe_plan

if TYPE_CHECKING:
    from agentarmor.orchestrator.planning.capabilities import TargetCapabilities
    from agentarmor.orchestrator.runner import RunnableProbe


def primary_owasp(probe: RunnableProbe) -> str:
    return probe.owasp[0] if probe.owasp else "LLM01"


def score_owasp_risk(owasp_failure_counts: dict[str, int], owasp_id: str) -> int:
    return owasp_failure_counts.get(owasp_id, 0)


def reorder_probes_by_risk(
    remaining: list[RunnableProbe],
    owasp_failure_counts: dict[str, int],
) -> list[RunnableProbe]:
    """Priority queue: categories with more early failures run first."""
    return sorted(
        remaining,
        key=lambda p: (
            -score_owasp_risk(owasp_failure_counts, primary_owasp(p)),
            p.layer,
            p.id,
        ),
    )


def adaptive_deep_probes(
    all_probes: list[RunnableProbe],
    *,
    owasp_ids: list[str],
    owasp_depths: dict[str, str],
    global_depth: str,
    capabilities: TargetCapabilities,
    owasp_failure_counts: dict[str, int],
    already_selected: set[str],
    failure_threshold: int = 2,
) -> tuple[list[RunnableProbe], dict[str, str], list[str]]:
    """
    Escalate depth to 'deep' for OWASP categories with repeated failures.
    Returns (new_probes, updated_depths, escalated_owasp_ids).
    """
    updated_depths = dict(owasp_depths)
    escalated: list[str] = []
    new_probes: list[RunnableProbe] = []

    for oid in owasp_ids:
        if owasp_failure_counts.get(oid, 0) < failure_threshold:
            continue
        current = updated_depths.get(oid, global_depth)
        if current == "deep":
            continue
        updated_depths[oid] = "deep"
        escalated.append(oid)

    if not escalated:
        return [], updated_depths, []

    plan = build_probe_plan(
        all_probes,
        owasp_ids=escalated,
        scan_depth="deep",
        owasp_depths=updated_depths,
        capabilities=capabilities,
    )
    for probe in plan.probes:
        if probe.id not in already_selected:
            new_probes.append(probe)
            already_selected.add(probe.id)

    return new_probes, updated_depths, escalated
