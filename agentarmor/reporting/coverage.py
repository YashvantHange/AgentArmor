"""OWASP coverage report from planner audit and executed probes."""

from __future__ import annotations

from typing import Any


def build_coverage_report(
    planner_audit: dict[str, Any] | None,
    executed_probe_ids: list[str],
) -> dict[str, float]:
    if not planner_audit:
        return {}
    by_owasp = planner_audit.get("probes_by_owasp")
    if not isinstance(by_owasp, dict):
        return {}

    executed = set(executed_probe_ids)
    report: dict[str, float] = {}
    for owasp_id, planned_ids in by_owasp.items():
        if not isinstance(planned_ids, list) or not planned_ids:
            continue
        ran = sum(1 for pid in planned_ids if pid in executed)
        report[owasp_id] = round(ran / len(planned_ids), 3)
    return report
