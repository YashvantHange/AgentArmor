"""Structural quality gates for red-team agents and skills."""

from __future__ import annotations

import re

import pytest

from agentarmor.attack.mutations.registry import MUTATION_REGISTRY
from agentarmor.redteam.agents.prompts import AGENT_PROMPTS
from agentarmor.redteam.agents.registry import all_agents, resolve_agent
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import TargetProfile
from agentarmor.redteam.skills.loader import load_skills, skill_for_node

_SECRET_PATTERN = re.compile(r"sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}", re.I)


def test_minimum_skill_count():
    assert len(load_skills()) >= 13


def test_all_skills_have_required_fields():
    for sid, skill in load_skills().items():
        assert skill.agent, sid
        assert skill.name, sid
        assert skill.seeds, sid
        assert skill.mutations, sid
        assert skill.owasp, sid
        assert all(o.startswith("LLM") for o in skill.owasp), sid


def test_mutations_exist_in_registry():
    for skill in load_skills().values():
        for mut in skill.mutations:
            assert mut in MUTATION_REGISTRY, f"{skill.id} uses {mut}"


def test_skills_map_to_registered_agents():
    agents = all_agents()
    for skill in load_skills().values():
        assert skill.agent in agents, skill.id


def test_every_agent_has_system_prompt():
    for agent_id in all_agents():
        assert agent_id in AGENT_PROMPTS
        assert len(AGENT_PROMPTS[agent_id]) > 50


def test_attack_graph_nodes_resolve():
    profile = TargetProfile(memory=True, rag=True, mcp=True, a2a=True, email_tool=True)
    for path in build_attack_graph(profile):
        for node in path.nodes:
            agent = resolve_agent(node.node_id)
            assert agent.agent_id


def test_node_skill_mapping_for_baselines():
    for node_id in ("prompt_injection", "system_prompt_leak", "mcp_enumeration", "a2a_handoff"):
        skill = skill_for_node(node_id)
        assert skill is not None, node_id


def test_no_real_secrets_in_seeds():
    for skill in load_skills().values():
        for seed in skill.seeds + skill.multi_turn:
            assert not _SECRET_PATTERN.search(seed), skill.id


def test_multi_turn_skills_have_two_plus_turns():
    for skill in load_skills().values():
        if skill.multi_turn:
            assert len(skill.multi_turn) >= 2, skill.id
            assert all(t.strip() for t in skill.multi_turn), skill.id
