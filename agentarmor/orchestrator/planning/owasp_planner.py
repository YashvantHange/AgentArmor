"""OWASP Top 10 probe planner with Quick / Standard / Deep depth tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentarmor.core.config import AppConfig
from agentarmor.knowledge.owasp_llm import OWASP_LLM
from agentarmor.orchestrator.planning.capabilities import TargetCapabilities, detect_capabilities_async
from agentarmor.orchestrator.planning.probe_catalog import LAYER_ORDER, probe_issue_type, probe_requires
from agentarmor.orchestrator.planning.work_units import estimate_duration_minutes, probe_work_units

if TYPE_CHECKING:
    from agentarmor.orchestrator.runner import RunnableProbe

PLANNER_VERSION = "2.0.0"

DEPTH_BUDGET: dict[str, int] = {
    "quick": 3,
    "standard": 6,
    "deep": 12,
}

DEFAULT_OWASP_IDS = [f"LLM{i:02d}" for i in range(1, 11)]


@dataclass
class SkippedProbe:
    id: str
    reason: str


@dataclass
class ProbePlanResult:
    probes: list[RunnableProbe]
    selected_ids: list[str]
    skipped: list[SkippedProbe]
    owasp_ids: list[str]
    depths: dict[str, str]
    capabilities: TargetCapabilities
    total_work_units: int
    estimated_duration_min: float
    estimated_probes: int
    probes_by_owasp: dict[str, list[str]]
    planner_version: str = PLANNER_VERSION

    def audit_dict(self) -> dict:
        return {
            "planner_version": self.planner_version,
            "inputs": {
                "owasp_ids": self.owasp_ids,
                "depths": self.depths,
                "capabilities": self.capabilities.to_dict(),
            },
            "selected_probes": self.selected_ids,
            "skipped_probes": [{"id": s.id, "reason": s.reason} for s in self.skipped],
            "execution_order": self.selected_ids,
            "probes_by_owasp": self.probes_by_owasp,
            "total_work_units": self.total_work_units,
            "estimated_duration_min": self.estimated_duration_min,
        }


def _depth_for_owasp(
    owasp_id: str,
    global_depth: str,
    per_category: dict[str, str],
) -> str:
    return per_category.get(owasp_id, global_depth)


def _layer_rank(layer: str) -> int:
    try:
        return LAYER_ORDER.index(layer)
    except ValueError:
        return len(LAYER_ORDER)


def _sort_probes(probes: list[RunnableProbe]) -> list[RunnableProbe]:
    return sorted(probes, key=lambda p: (_layer_rank(p.layer), p.id))


def _probes_for_owasp(all_probes: list[RunnableProbe], owasp_id: str) -> list[RunnableProbe]:
    return [p for p in all_probes if owasp_id in p.owasp]


def build_probe_plan(
    all_probes: list[RunnableProbe],
    *,
    owasp_ids: list[str] | None = None,
    scan_depth: str = "standard",
    owasp_depths: dict[str, str] | None = None,
    capabilities: TargetCapabilities | None = None,
) -> ProbePlanResult:
    """Select probes by OWASP category and depth; filter by target capabilities."""
    owasp_ids = owasp_ids or list(DEFAULT_OWASP_IDS)
    owasp_depths = owasp_depths or {}
    caps = capabilities or TargetCapabilities()

    selected: dict[str, RunnableProbe] = {}
    skipped: list[SkippedProbe] = []
    probes_by_owasp: dict[str, list[str]] = {}

    for oid in owasp_ids:
        if oid not in OWASP_LLM:
            continue
        depth = _depth_for_owasp(oid, scan_depth, owasp_depths)
        budget = DEPTH_BUDGET.get(depth, DEPTH_BUDGET["standard"])
        candidates = _sort_probes(_probes_for_owasp(all_probes, oid))
        picked: list[str] = []
        for probe in candidates:
            if len(picked) >= budget:
                break
            reqs = probe_requires(probe.id)
            if not caps.satisfied(reqs):
                skipped.append(SkippedProbe(probe.id, f"requires_{'+'.join(reqs) or 'unknown'}"))
                continue
            if probe.id not in selected:
                selected[probe.id] = probe
            if probe.id not in picked:
                picked.append(probe.id)
        probes_by_owasp[oid] = picked

    # Standard scan with all OWASP: ensure ~50 probes by adding more L0 per category
    target_min = 45 if scan_depth == "standard" and len(owasp_ids) >= 8 else 0
    if target_min and len(selected) < target_min:
        for oid in owasp_ids:
            if len(selected) >= 50:
                break
            depth = _depth_for_owasp(oid, scan_depth, owasp_depths)
            if depth == "quick":
                continue
            extra_budget = DEPTH_BUDGET.get("deep", 12) - len(probes_by_owasp.get(oid, []))
            if extra_budget <= 0:
                continue
            for probe in _sort_probes(_probes_for_owasp(all_probes, oid)):
                if len(selected) >= 50:
                    break
                if probe.id in selected:
                    continue
                reqs = probe_requires(probe.id)
                if not caps.satisfied(reqs):
                    continue
                selected[probe.id] = probe
                probes_by_owasp.setdefault(oid, []).append(probe.id)
                extra_budget -= 1
                if extra_budget <= 0:
                    break

    ordered = _sort_probes(list(selected.values()))
    selected_ids = [p.id for p in ordered]
    total_units = sum(probe_work_units(p.layer) for p in ordered)

    return ProbePlanResult(
        probes=ordered,
        selected_ids=selected_ids,
        skipped=skipped,
        owasp_ids=owasp_ids,
        depths={oid: _depth_for_owasp(oid, scan_depth, owasp_depths) for oid in owasp_ids},
        capabilities=caps,
        total_work_units=total_units,
        estimated_duration_min=estimate_duration_minutes(total_units),
        estimated_probes=len(ordered),
        probes_by_owasp=probes_by_owasp,
    )


async def plan_probes_for_config(
    config: AppConfig,
    all_probes: list[RunnableProbe],
) -> ProbePlanResult:
    caps = await detect_capabilities_async(config)
    planner = config.planner
    return build_probe_plan(
        all_probes,
        owasp_ids=planner.owasp_ids or None,
        scan_depth=planner.scan_depth,
        owasp_depths=planner.owasp_depths,
        capabilities=caps,
    )
