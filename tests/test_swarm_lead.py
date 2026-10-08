"""Lead agent: deterministic by default, LLM-planned only when enabled."""

from __future__ import annotations

import asyncio
import json

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import TargetProfile
from agentarmor.swarm.goals import get_swarm_goal
from agentarmor.swarm.lead import LeadAgent, SwarmPlan
from agentarmor.swarm.roster import build_roster


def _profile() -> TargetProfile:
    return TargetProfile(tool_access=True, rag=True, memory=True, mcp=True, a2a=True)


def _lead() -> LeadAgent:
    goal = get_swarm_goal("extract_system_prompt")
    assert goal is not None
    profile = _profile()
    return LeadAgent(goal, profile, build_attack_graph(profile))


def _config(*, lead_llm: bool = False) -> AppConfig:
    cfg = AppConfig()
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.api_key = "test-key"
    cfg.swarm.lead_llm_enabled = lead_llm
    return cfg


# --- the default path -------------------------------------------------------


def test_the_llm_call_is_off_by_default():
    assert AppConfig().swarm.lead_llm_enabled is False


def test_planning_makes_no_model_call_by_default(monkeypatch):
    """A swarm must never depend on an LLM to start."""

    def explode(*_a, **_k):
        raise AssertionError("the lead must not call a model unless enabled")

    monkeypatch.setattr("litellm.acompletion", explode, raising=False)
    plan = asyncio.run(_lead().plan(_config()))
    assert plan.llm_planned is False
    assert plan.note == "graph-ordered"
    assert plan.subgoals


def test_the_deterministic_plan_follows_graph_order():
    lead = _lead()
    plan = lead.deterministic_plan()
    assert [s.node_id for s in plan.subgoals] == [n.node_id for n in lead.candidate_nodes()]


def test_the_deterministic_plan_is_stable():
    first = _lead().deterministic_plan()
    second = _lead().deterministic_plan()
    assert first == second


def test_subgoals_are_bounded():
    for sub in _lead().deterministic_plan().subgoals:
        assert sub.text.strip()
        assert len(sub.text) <= 160
        assert 0.0 <= sub.priority <= 1.0


# --- the opt-in path --------------------------------------------------------


def _fake_completion(payload):
    async def call(config, budget, *, system, user, agent_name, **kwargs):
        call.user = user  # type: ignore[attr-defined]
        return payload, {}

    return call


def test_an_enabled_lead_shapes_the_plan(monkeypatch):
    lead = _lead()
    first_node = lead.candidate_nodes()[0].node_id
    fake = _fake_completion(
        {"subgoals": [{"node_id": first_node, "text": "lead wording", "priority": 0.9}]}
    )
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)

    plan = asyncio.run(lead.plan(_config(lead_llm=True)))
    assert plan.llm_planned is True
    assert plan.note == "lead-planned"
    assert [s.node_id for s in plan.subgoals] == [first_node]
    assert plan.subgoals[0].text == "lead wording"


def test_hallucinated_node_ids_are_dropped(monkeypatch):
    """An invented node has no skill and no judge rubric; it would fail at execution."""
    lead = _lead()
    real = lead.candidate_nodes()[0].node_id
    fake = _fake_completion(
        {
            "subgoals": [
                {"node_id": "totally_made_up_node", "text": "nope", "priority": 1.0},
                {"node_id": real, "text": "fine", "priority": 0.5},
            ]
        }
    )
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)

    plan = asyncio.run(lead.plan(_config(lead_llm=True)))
    assert [s.node_id for s in plan.subgoals] == [real]


def test_only_hallucinations_falls_back_to_graph_order(monkeypatch):
    fake = _fake_completion({"subgoals": [{"node_id": "invented", "text": "x"}]})
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)
    plan = asyncio.run(_lead().plan(_config(lead_llm=True)))
    assert plan.llm_planned is False
    assert plan.note == "graph-ordered"


@pytest.mark.parametrize("payload", [None, {}, {"subgoals": []}, {"subgoals": "nope"}])
def test_a_failed_or_empty_call_falls_back(monkeypatch, payload):
    """A swarm never fails because planning failed."""
    monkeypatch.setattr(
        "agentarmor.redteam.llm_client.completion_json", _fake_completion(payload)
    )
    plan = asyncio.run(_lead().plan(_config(lead_llm=True)))
    assert plan.llm_planned is False
    assert plan.subgoals, "the fallback must still produce a usable plan"


def test_the_prompt_supplies_the_allowed_node_ids(monkeypatch):
    lead = _lead()
    fake = _fake_completion({"subgoals": []})
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)
    asyncio.run(lead.plan(_config(lead_llm=True)))
    assert "available_node_ids" in fake.user  # type: ignore[attr-defined]
    assert lead.candidate_nodes()[0].node_id in fake.user  # type: ignore[attr-defined]


def test_out_of_range_priorities_are_clamped(monkeypatch):
    lead = _lead()
    node = lead.candidate_nodes()[0].node_id
    fake = _fake_completion(
        {"subgoals": [{"node_id": node, "text": "t", "priority": 99.0}]}
    )
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)
    plan = asyncio.run(lead.plan(_config(lead_llm=True)))
    assert plan.subgoals[0].priority == 1.0


def test_a_non_numeric_priority_does_not_raise(monkeypatch):
    lead = _lead()
    node = lead.candidate_nodes()[0].node_id
    fake = _fake_completion(
        {"subgoals": [{"node_id": node, "text": "t", "priority": "high"}]}
    )
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)
    plan = asyncio.run(lead.plan(_config(lead_llm=True)))
    assert plan.subgoals[0].priority == 0.5


def test_long_subgoal_text_is_truncated(monkeypatch):
    lead = _lead()
    node = lead.candidate_nodes()[0].node_id
    fake = _fake_completion({"subgoals": [{"node_id": node, "text": "z" * 900}]})
    monkeypatch.setattr("agentarmor.redteam.llm_client.completion_json", fake)
    plan = asyncio.run(lead.plan(_config(lead_llm=True)))
    assert len(plan.subgoals[0].text) == 160


# --- assignment -------------------------------------------------------------


def test_assignment_applies_wording_and_priority():
    lead = _lead()
    goal = get_swarm_goal("extract_system_prompt")
    assert goal is not None
    roster = build_roster(goal, _profile(), size=12)
    target_node = roster[0].node_id
    plan = SwarmPlan(
        goal_id=goal.id,
        subgoals=[{"node_id": target_node, "text": "assigned text", "priority": 0.77}],  # type: ignore[list-item]
    )
    lead.assign(plan, roster)

    touched = [m for m in roster if m.node_id == target_node]
    assert touched
    for member in touched:
        assert member.subgoal == "assigned text"
        assert member.priority == 0.77


def test_assignment_never_blanks_an_unmentioned_member():
    lead = _lead()
    goal = get_swarm_goal("extract_system_prompt")
    assert goal is not None
    roster = build_roster(goal, _profile(), size=12)
    before = {m.member_id: m.subgoal for m in roster}
    lead.assign(SwarmPlan(goal_id=goal.id, subgoals=[]), roster)
    for member in roster:
        assert member.subgoal == before[member.member_id]
        assert member.subgoal.strip()


def test_assignment_does_not_move_a_member_to_another_node():
    """The plan supplies wording and priority; the roster owns node assignment."""
    lead = _lead()
    goal = get_swarm_goal("extract_system_prompt")
    assert goal is not None
    roster = build_roster(goal, _profile(), size=10)
    nodes_before = [m.node_id for m in roster]
    lead.assign(lead.deterministic_plan(), roster)
    assert [m.node_id for m in roster] == nodes_before


def test_plan_serialises():
    plan = _lead().deterministic_plan()
    assert json.loads(plan.model_dump_json())["goal_id"] == "extract_system_prompt"
