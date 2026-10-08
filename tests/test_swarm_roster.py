"""Roster construction and the member agent."""

from __future__ import annotations

import asyncio

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.attack import _llm_mixin
from agentarmor.redteam.agents.base import BaseAttackAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import TargetProfile
from agentarmor.redteam.skills.loader import get_skill
from agentarmor.redteam.untrusted import UNTRUSTED_NOTICE
from agentarmor.swarm.blackboard import Blackboard
from agentarmor.swarm.goals import get_swarm_goal, list_swarm_goals
from agentarmor.swarm.member import SwarmMemberAgent, build_system_suffix, plan_for
from agentarmor.swarm.personas import PERSONA_LIBRARY
from agentarmor.swarm.roster import STRATEGIES, build_roster, compute_coverage
from agentarmor.swarm.schemas import Fact, fact_id_for

GOAL = "extract_system_prompt"


def _full_profile() -> TargetProfile:
    return TargetProfile(
        tool_access=True,
        rag=True,
        memory=True,
        mcp=True,
        a2a=True,
        email_tool=True,
        tools=["send_email", "lookup_order"],
    )


def _goal(goal_id: str = GOAL):
    goal = get_swarm_goal(goal_id)
    assert goal is not None
    return goal


# --- size and distinctness ---------------------------------------------------


@pytest.mark.parametrize("goal", [g.id for g in list_swarm_goals()])
@pytest.mark.parametrize("profile_name", ["full", "bare"])
def test_every_goal_reaches_the_ceiling_on_any_profile(goal, profile_name):
    """A narrow goal on a shallow profile must still fill the roster.

    extract_system_prompt matches only two nodes on a bare endpoint, which caps
    well below 100 from goal-relevant nodes alone.
    """
    profile = _full_profile() if profile_name == "full" else TargetProfile()
    members = build_roster(_goal(goal), profile, size=100)
    assert len(members) == 100


def test_members_are_distinct():
    members = build_roster(_goal(), _full_profile(), size=100)
    assert len({m.member_id for m in members}) == 100
    tuples = {(m.node_id, m.skill_id, m.persona_id, m.strategy) for m in members}
    assert len(tuples) == 100, "members must differ by more than their id"


def test_member_ids_are_contiguous_and_namespaced():
    members = build_roster(_goal(), _full_profile(), size=12)
    assert [m.member_id for m in members] == [f"sw-{i:03d}" for i in range(1, 13)]


def test_roster_is_deterministic():
    """Reproducibility matters for a security tool, so no RNG."""
    first = build_roster(_goal(), _full_profile(), size=40)
    second = build_roster(_goal(), _full_profile(), size=40)
    assert first == second


def test_smaller_rosters_are_prefixes_of_larger_ones():
    large = build_roster(_goal(), _full_profile(), size=40)
    small = build_roster(_goal(), _full_profile(), size=10)
    assert [m.model_dump() for m in small] == [m.model_dump() for m in large[:10]]


@pytest.mark.parametrize("size", [0, -1, -100])
def test_non_positive_size_yields_no_members(size):
    assert build_roster(_goal(), _full_profile(), size=size) == []


def test_size_one_works():
    members = build_roster(_goal(), _full_profile(), size=1)
    assert len(members) == 1


def test_size_beyond_the_available_slots_is_truncated_not_padded():
    only_one = [PERSONA_LIBRARY[0]]
    members = build_roster(_goal(), TargetProfile(), size=1000, personas=only_one)
    assert 0 < len(members) < 1000
    assert len({m.member_id for m in members}) == len(members)


# --- every member must be executable ----------------------------------------


def test_every_member_has_a_resolvable_skill():
    """The compile-time guarantee against the runtime ValueError.

    generate_from_skill raises when no skill serves a node, and the red-team loop
    does not catch it, so a missing skill kills a whole scan. Dropping those slots
    at construction means it can never reach execution.
    """
    for profile in (_full_profile(), TargetProfile()):
        for member in build_roster(_goal(), profile, size=100):
            assert get_skill(member.skill_id) is not None, member.skill_id


def test_every_member_names_a_real_persona():
    known = {p.id for p in PERSONA_LIBRARY}
    for member in build_roster(_goal(), _full_profile(), size=100):
        assert member.persona_id in known


def test_every_member_uses_a_known_strategy():
    for member in build_roster(_goal(), _full_profile(), size=100):
        assert member.strategy in STRATEGIES


def test_every_member_carries_a_subgoal():
    for member in build_roster(_goal(), _full_profile(), size=30):
        assert member.subgoal.strip()


# --- ordering ---------------------------------------------------------------


def test_the_first_wave_spans_multiple_attack_paths():
    """Otherwise wave one drains the highest-ranked path and learns less."""
    members = build_roster(_goal(), _full_profile(), size=8)
    assert len({m.path_id for m in members}) >= 3


def test_the_opening_members_use_the_plain_strategy():
    """A roster that opens with indirection has no baseline to compare against."""
    members = build_roster(_goal(), _full_profile(), size=8)
    assert all(m.strategy == "direct" for m in members)


def test_goal_relevant_nodes_are_used_before_the_remainder():
    goal = _goal()
    members = build_roster(goal, _full_profile(), size=10)
    goal_codes = {c.upper() for c in goal.owasp}
    assert any(goal_codes & {c.upper() for c in m.owasp} for m in members[:3])


def test_nodes_come_from_the_supplied_graph():
    profile = _full_profile()
    valid = {n.node_id for p in build_attack_graph(profile) for n in p.nodes}
    for member in build_roster(_goal(), profile, size=50):
        assert member.node_id in valid


# --- coverage ---------------------------------------------------------------


def test_coverage_matches_the_roster():
    members = build_roster(_goal(), _full_profile(), size=40)
    coverage = compute_coverage(members, concurrency=8)
    assert coverage.agents == 40
    assert coverage.personas == len({m.persona_id for m in members})
    assert coverage.nodes == len({m.node_id for m in members})
    assert coverage.attack_paths == len({m.path_id for m in members})
    assert coverage.strategies == len({m.strategy for m in members})
    assert coverage.concurrency == 8


def test_coverage_exposes_a_shallow_graph_honestly():
    """A big roster on a bare endpoint is mostly persona variation. Say so."""
    members = build_roster(_goal(), TargetProfile(), size=100)
    coverage = compute_coverage(members, concurrency=8)
    assert coverage.agents == 100
    assert coverage.nodes < 20, "a bare endpoint exposes only the baseline nodes"
    assert "Attack paths" in coverage.summary_line()


# --- the member agent -------------------------------------------------------


def test_member_agent_satisfies_the_base_contract():
    member = build_roster(_goal(), _full_profile(), size=1)[0]
    agent = SwarmMemberAgent(member, Blackboard())
    assert isinstance(agent, BaseAttackAgent)
    assert agent.agent_id == member.member_id
    assert agent.judge_rubric_for(member.node_id)


def test_member_id_namespace_is_distinct_from_base_agents():
    """Three "agent" taxonomies exist; sw-NNN keeps members unambiguous."""
    from agentarmor.redteam.agents.registry import list_agent_ids

    member = build_roster(_goal(), _full_profile(), size=1)[0]
    agent = SwarmMemberAgent(member, Blackboard())
    assert agent.agent_id.startswith("sw-")
    assert agent.agent_id not in set(list_agent_ids())


def test_system_suffix_carries_persona_and_subgoal():
    member = build_roster(_goal(), _full_profile(), size=1)[0]
    suffix = build_system_suffix(member)
    assert member.subgoal in suffix
    assert len(suffix) <= 400


def test_plan_for_carries_the_subgoal_into_the_rationale():
    member = build_roster(_goal(), _full_profile(), size=1)[0]
    plan = plan_for(member)
    assert plan.next_node == member.node_id
    assert plan.path_id == member.path_id
    assert plan.strategy == member.strategy
    assert plan.rationale == member.subgoal


def _cloud_config() -> AppConfig:
    cfg = AppConfig()
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.api_key = "test-key"
    return cfg


def test_member_generation_passes_its_parameters_through(monkeypatch):
    captured: dict = {}

    async def fake_completion(config, budget, *, system, user, agent_name, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured.update(kwargs)
        return {"prompt": "crafted"}, {}

    monkeypatch.setattr(_llm_mixin, "completion_json", fake_completion)
    cfg = _cloud_config()
    member = build_roster(_goal(), _full_profile(), size=1)[0]
    agent = SwarmMemberAgent(member, Blackboard())

    asyncio.run(
        agent.generate(cfg, BudgetGovernor(cfg.redteam.budget), _full_profile(), plan_for(member))
    )

    assert f"skill: {member.skill_id}" in captured["user"]
    assert captured["temperature"] == member.temperature
    assert member.subgoal in captured["system"]
    # The untrusted notice must precede the persona framing.
    assert captured["system"].index(UNTRUSTED_NOTICE) < captured["system"].index(member.subgoal)


def test_a_member_sees_other_members_facts(monkeypatch):
    captured: dict = {}

    async def fake_completion(config, budget, *, system, user, agent_name, **kwargs):
        captured["user"] = user
        return {"prompt": "crafted"}, {}

    monkeypatch.setattr(_llm_mixin, "completion_json", fake_completion)
    cfg = _cloud_config()
    members = build_roster(_goal(), _full_profile(), size=3)
    board = Blackboard()

    async def run():
        await board.publish(
            [
                Fact(
                    fact_id=fact_id_for("secret", "CANARY_SECRET_9f3a2b"),
                    kind="secret",
                    value="CANARY_SECRET_9f3a2b",
                    source_member_id=members[0].member_id,
                    provenance="verified",
                    confidence=0.9,
                )
            ]
        )
        agent = SwarmMemberAgent(members[2], board)
        await agent.generate(
            cfg, BudgetGovernor(cfg.redteam.budget), _full_profile(), plan_for(members[2])
        )

    asyncio.run(run())
    assert "CANARY_SECRET_9f3a2b" in captured["user"]
    assert '<shared_observations trust="untrusted">' in captured["user"]


def test_the_brief_is_snapshotted_once():
    """A fact published mid-flight must not change a running member's context."""

    async def run():
        board = Blackboard()
        members = build_roster(_goal(), _full_profile(), size=2)
        agent = SwarmMemberAgent(members[1], board)
        first = await agent.take_brief()
        await board.publish(
            [
                Fact(
                    fact_id=fact_id_for("secret", "LATE_ARRIVAL"),
                    kind="secret",
                    value="LATE_ARRIVAL",
                    source_member_id=members[0].member_id,
                    provenance="verified",
                    confidence=0.9,
                )
            ]
        )
        return first, await agent.take_brief()

    first, second = asyncio.run(run())
    assert first == second == ""


def test_a_member_never_sees_its_own_fact():
    async def run():
        board = Blackboard()
        member = build_roster(_goal(), _full_profile(), size=1)[0]
        await board.publish(
            [
                Fact(
                    fact_id=fact_id_for("secret", "SELF_FOUND"),
                    kind="secret",
                    value="SELF_FOUND",
                    source_member_id=member.member_id,
                    provenance="verified",
                    confidence=0.9,
                )
            ]
        )
        return await SwarmMemberAgent(member, board).take_brief()

    assert asyncio.run(run()) == ""
