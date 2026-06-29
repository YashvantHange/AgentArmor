"""Work-unit weights for ETA and plan estimation."""

from __future__ import annotations

WORK_UNITS_BY_LAYER: dict[str, int] = {
    "L1": 1,
    "L2": 2,
    "L3": 5,
    "L0": 3,
    "plugin": 2,
    "agent": 2,
    "mcp": 2,
    "rag": 3,
    "self_play": 8,
    "web": 2,
}

# Average seconds per work unit (calibrated default; observability can refine)
SECONDS_PER_WORK_UNIT: float = 8.0


def probe_work_units(layer: str) -> int:
    return WORK_UNITS_BY_LAYER.get(layer, 1)


def estimate_duration_minutes(total_units: int) -> float:
    return round((total_units * SECONDS_PER_WORK_UNIT) / 60.0, 1)


def remaining_by_layer(probes: list, completed_ids: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in probes:
        if p.id in completed_ids:
            continue
        layer = getattr(p, "layer", "L1")
        counts[layer] = counts.get(layer, 0) + 1
    return counts
