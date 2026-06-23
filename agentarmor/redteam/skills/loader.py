"""Load red-team skill definitions from YAML bundles."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_SKILLS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class SkillDef:
    id: str
    agent: str
    name: str
    owasp: list[str]
    seeds: list[str]
    mutations: list[str]
    node_ids: list[str]
    bypass_techniques: list[str]
    judge_rubric: str
    multi_turn: list[str]


def _parse_skill(skill_id: str, spec: dict) -> SkillDef:
    return SkillDef(
        id=skill_id,
        agent=str(spec["agent"]),
        name=str(spec["name"]),
        owasp=list(spec.get("owasp") or []),
        seeds=list(spec.get("seeds") or []),
        mutations=list(spec.get("mutations") or []),
        node_ids=list(spec.get("node_ids") or [skill_id]),
        bypass_techniques=list(spec.get("bypass_techniques") or []),
        judge_rubric=str(spec.get("judge_rubric") or ""),
        multi_turn=list(spec.get("multi_turn") or []),
    )


@lru_cache(maxsize=1)
def load_skills() -> dict[str, SkillDef]:
    skills: dict[str, SkillDef] = {}
    for path in sorted(_SKILLS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        for skill_id, spec in raw.items():
            if isinstance(spec, dict):
                skills[skill_id] = _parse_skill(skill_id, spec)
    return skills


def get_skill(skill_id: str) -> SkillDef | None:
    return load_skills().get(skill_id)


def skill_for_node(node_id: str, agent_id: str | None = None) -> SkillDef | None:
    for skill in load_skills().values():
        if agent_id and skill.agent != agent_id:
            continue
        if node_id in skill.node_ids or node_id == skill.id:
            return skill
    for skill in load_skills().values():
        if node_id in skill.node_ids or node_id == skill.id:
            return skill
    return None


def skills_for_agent(agent_id: str) -> list[SkillDef]:
    return [s for s in load_skills().values() if s.agent == agent_id]
