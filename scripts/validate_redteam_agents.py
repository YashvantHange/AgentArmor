#!/usr/bin/env python3
"""Validate red-team agent skills, registry, and attack graph coverage."""

from __future__ import annotations

import re
import sys

from agentarmor.attack.mutations.registry import MUTATION_REGISTRY
from agentarmor.redteam.agents.prompts import AGENT_PROMPTS
from agentarmor.redteam.agents.registry import all_agents, resolve_agent
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import TargetProfile
from agentarmor.redteam.skills.loader import load_skills

_SECRET_PATTERN = re.compile(r"sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}", re.I)


def main() -> int:
    errors: list[str] = []
    skills = load_skills()

    if len(skills) < 13:
        errors.append(f"Expected >=13 skills, got {len(skills)}")

    for sid, skill in skills.items():
        if not skill.agent or not skill.name or not skill.seeds:
            errors.append(f"Skill {sid}: missing agent/name/seeds")
        if not skill.owasp:
            errors.append(f"Skill {sid}: missing owasp")
        if not skill.mutations:
            errors.append(f"Skill {sid}: missing mutations")
        for mut in skill.mutations:
            if mut not in MUTATION_REGISTRY:
                errors.append(f"Skill {sid}: unknown mutation {mut}")
        if skill.agent not in all_agents():
            errors.append(f"Skill {sid}: agent {skill.agent} not in registry")
        for seed in skill.seeds:
            if _SECRET_PATTERN.search(seed):
                errors.append(f"Skill {sid}: seed looks like real credential")
        if skill.multi_turn and len(skill.multi_turn) < 2:
            errors.append(f"Skill {sid}: multi_turn needs >=2 turns")

    for agent_id in all_agents():
        if agent_id not in AGENT_PROMPTS or not AGENT_PROMPTS[agent_id].strip():
            errors.append(f"Agent {agent_id}: missing system prompt")

    profile = TargetProfile(memory=True, rag=True, mcp=True, a2a=True, email_tool=True)
    for path in build_attack_graph(profile):
        for node in path.nodes:
            try:
                agent = resolve_agent(node.node_id)
                if not agent.agent_id:
                    errors.append(f"Node {node.node_id}: agent has no id")
            except Exception as exc:
                errors.append(f"Node {node.node_id}: resolve failed — {exc}")

    if errors:
        print("REDTEAM VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(skills)} skills, {len(all_agents())} agents, graph nodes resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
