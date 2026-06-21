"""Load attack goal definitions from goals.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AttackGoalDef:
    id: str
    name: str
    owasp: list[str]
    seeds: list[str]
    mutations: list[str]


@lru_cache(maxsize=1)
def load_goals() -> dict[str, AttackGoalDef]:
    path = Path(__file__).parent / "goals.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    goals: dict[str, AttackGoalDef] = {}
    for goal_id, spec in raw.items():
        goals[goal_id] = AttackGoalDef(
            id=goal_id,
            name=spec["name"],
            owasp=list(spec.get("owasp", [])),
            seeds=list(spec.get("seeds", [])),
            mutations=list(spec.get("mutations", [])),
        )
    return goals


def get_goal(goal_id: str) -> AttackGoalDef | None:
    return load_goals().get(goal_id)
