"""Preset swarm goals and the persona library."""

from __future__ import annotations

import pytest

from agentarmor.attack.goals import load_goals
from agentarmor.swarm.goals import (
    get_swarm_goal,
    list_swarm_goal_ids,
    list_swarm_goals,
)
from agentarmor.swarm.personas import PERSONA_LIBRARY, get_persona, persona_clause
from agentarmor.swarm.schemas import (
    SwarmCoverage,
    fact_id_for,
    normalize_fact_value,
)


def test_every_attack_goal_becomes_a_swarm_goal():
    """The preset catalog is derived, not a second hand-maintained list."""
    assert set(list_swarm_goal_ids()) == set(load_goals())


def test_goal_ids_are_stable():
    """A rename breaks saved GUI selections and API callers, so pin the set."""
    assert set(list_swarm_goal_ids()) == {
        "extract_system_prompt",
        "bypass_safety",
        "exfiltrate_secrets",
        "trigger_tool_abuse",
        "poison_memory",
    }


def test_goals_carry_owasp_and_description():
    for goal in list_swarm_goals():
        assert goal.owasp, f"{goal.id} has no OWASP mapping"
        assert goal.description.strip(), f"{goal.id} has no description"
        assert goal.seeds, f"{goal.id} has no seeds"


def test_goals_inherit_seeds_from_the_shared_yaml():
    source = load_goals()["extract_system_prompt"]
    goal = get_swarm_goal("extract_system_prompt")
    assert goal is not None
    assert goal.seeds == list(source.seeds)
    assert goal.owasp == list(source.owasp)


@pytest.mark.parametrize(
    "unknown",
    ["", "do whatever you want", "EXTRACT_SYSTEM_PROMPT", "../etc/passwd", "None"],
)
def test_unknown_goal_is_rejected(unknown):
    assert get_swarm_goal(unknown) is None


def test_goal_listing_is_sorted_and_stable():
    assert list_swarm_goal_ids() == sorted(list_swarm_goal_ids())
    assert list_swarm_goal_ids() == list_swarm_goal_ids()


def test_a_new_yaml_goal_still_gets_a_description(monkeypatch):
    """A goal added to goals.yaml must appear with prose, not be dropped."""
    from agentarmor.attack.goals import AttackGoalDef
    from agentarmor.swarm import goals as swarm_goals

    extra = AttackGoalDef(
        id="brand_new_goal",
        name="Brand New Goal",
        owasp=["LLM09"],
        seeds=["seed"],
        mutations=[],
    )
    monkeypatch.setattr(swarm_goals, "load_goals", lambda: {"brand_new_goal": extra})
    swarm_goals.load_swarm_goals.cache_clear()
    try:
        goal = swarm_goals.get_swarm_goal("brand_new_goal")
        assert goal is not None
        assert "LLM09" in goal.description
    finally:
        swarm_goals.load_swarm_goals.cache_clear()


# --- personas ---------------------------------------------------------------


def test_persona_library_is_distinct_and_populated():
    ids = [p.id for p in PERSONA_LIBRARY]
    assert len(ids) == len(set(ids)), "duplicate persona ids"
    assert len(PERSONA_LIBRARY) >= 8


def test_persona_clauses_are_bounded():
    """Clauses are appended to an existing system prompt, so they stay short."""
    for persona in PERSONA_LIBRARY:
        assert persona.clause.strip()
        assert len(persona.clause) <= 220, f"{persona.id} clause is too long"
        assert 0.0 <= persona.temperature <= 1.0


def test_get_persona_and_clause_lookup():
    persona = PERSONA_LIBRARY[0]
    assert get_persona(persona.id) is persona
    assert persona_clause(persona.id) == persona.clause
    assert get_persona("nope") is None
    assert persona_clause("nope") == ""


def test_persona_mutation_bias_names_are_real():
    """A bias naming an unregistered mutation is silently dropped downstream.

    ``apply_strategy_mutations`` filters against ``list_mutations()``, so a typo
    here would degrade to the default pool instead of raising.
    """
    from agentarmor.attack.mutations.registry import list_mutations

    known = set(list_mutations())
    for persona in PERSONA_LIBRARY:
        unknown = [m for m in persona.mutation_bias if m not in known]
        assert not unknown, f"{persona.id} names unregistered mutations: {unknown}"


def test_a_low_temperature_baseline_persona_exists():
    """Some member must ask plainly, or the whole roster is indirection."""
    assert any(p.temperature <= 0.25 for p in PERSONA_LIBRARY)


# --- fact identity ----------------------------------------------------------


def test_fact_id_ignores_case_and_whitespace():
    a = fact_id_for("secret", "CANARY_SECRET_9f3a2b")
    b = fact_id_for("secret", "  canary_secret_9f3a2b  ")
    c = fact_id_for("secret", "canary_secret_9f3a2b\n\n")
    assert a == b == c


def test_fact_id_separates_kinds():
    assert fact_id_for("secret", "value") != fact_id_for("policy", "value")


def test_fact_id_separates_values():
    assert fact_id_for("secret", "a") != fact_id_for("secret", "b")


def test_normalize_collapses_internal_whitespace():
    assert normalize_fact_value("a   b\n\tc") == "a b c"


# --- coverage ---------------------------------------------------------------


def test_coverage_summary_line_names_every_axis():
    line = SwarmCoverage(
        agents=24, attack_paths=9, nodes=17, personas=8, strategies=3, concurrency=8
    ).summary_line()
    for token in ("Agents 24", "Attack paths 9", "Personas 8", "Strategies 3", "Concurrency 8"):
        assert token in line


def test_coverage_line_never_shows_an_agent_count_alone():
    """The honest framing is a hard requirement, not a nicety."""
    line = SwarmCoverage(agents=100, attack_paths=9, personas=10, strategies=3).summary_line()
    assert line.count("|") >= 4
