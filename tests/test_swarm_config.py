"""Swarm configuration: TOML wiring, clamps, and budget compatibility."""

from __future__ import annotations

import pytest

from agentarmor.core.config import (
    SWARM_MAX_COST_CEILING,
    SWARM_MAX_TOKENS_CEILING,
    AppConfig,
    SwarmBudgetConfig,
    apply_swarm_options,
    load_config,
)
from agentarmor.redteam.budget.governor import BudgetGovernor


def test_defaults_are_present_without_a_toml_file():
    sw = AppConfig().swarm
    assert sw.enabled is True
    assert sw.default_agents == 24
    assert sw.max_agents == 100
    assert sw.default_concurrent == 8
    assert sw.max_concurrent == 16
    assert sw.lead_llm_enabled is False


def test_default_agents_is_below_the_ceiling():
    """The common case must not be the slowest and most expensive one."""
    sw = AppConfig().swarm
    assert sw.default_agents < sw.max_agents
    assert sw.default_concurrent < sw.max_concurrent


def test_toml_section_loads(tmp_path):
    """Guards the third wiring point.

    ``load_config`` is a hand-written mapper, so a new section is silently
    discarded unless it is passed to the ``AppConfig(...)`` call. Without this
    test that omission looks like working code: the section parses, the model has
    defaults, and nothing raises.
    """
    path = tmp_path / "AgentArmor.toml"
    path.write_text(
        """
[target]
type = "endpoint"
url = "http://localhost:8000/v1/chat/completions"

[swarm]
default_agents = 40
max_agents = 64
default_concurrent = 12
max_concurrent = 12
max_swarms_per_day = 2
lead_llm_enabled = true

[swarm.budget]
max_tokens = 123456
max_cost_usd = 3.5

[swarm.blackboard]
max_facts = 50
brief_max_chars = 120
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.swarm.default_agents == 40
    assert cfg.swarm.max_agents == 64
    assert cfg.swarm.default_concurrent == 12
    assert cfg.swarm.max_swarms_per_day == 2
    assert cfg.swarm.lead_llm_enabled is True
    assert cfg.swarm.budget.max_tokens == 123456
    assert cfg.swarm.budget.max_cost_usd == 3.5
    assert cfg.swarm.blackboard.max_facts == 50
    assert cfg.swarm.blackboard.brief_max_chars == 120
    # Not overridden in the file, so the model default survives.
    assert cfg.swarm.blackboard.max_fact_chars == 160


def test_missing_swarm_section_uses_defaults(tmp_path):
    path = tmp_path / "AgentArmor.toml"
    path.write_text('[target]\ntype = "endpoint"\n', encoding="utf-8")
    assert load_config(path).swarm.default_agents == 24


def test_shipped_toml_parses():
    """The repository's own AgentArmor.toml must round-trip."""
    from pathlib import Path

    shipped = Path(__file__).resolve().parents[1] / "AgentArmor.toml"
    cfg = load_config(shipped)
    assert cfg.swarm.max_agents == 100
    assert cfg.swarm.budget.max_tokens == 250_000
    assert cfg.swarm.blackboard.max_facts == 200


def test_env_substitution_applies_to_the_swarm_section(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_TEST_AGENTS", "17")
    path = tmp_path / "AgentArmor.toml"
    path.write_text(
        '[target]\ntype = "endpoint"\n\n[swarm]\ndefault_agents = "${SWARM_TEST_AGENTS}"\n',
        encoding="utf-8",
    )
    assert load_config(path).swarm.default_agents == 17


@pytest.mark.parametrize(
    "requested,expected",
    [(500, 100), (101, 100), (100, 100), (24, 24), (1, 1), (0, 1), (-5, 1)],
)
def test_agent_count_is_clamped_both_ways(requested, expected):
    _, agents, _ = apply_swarm_options(AppConfig(), agents=requested)
    assert agents == expected


@pytest.mark.parametrize("requested,expected", [(99, 16), (17, 16), (16, 16), (1, 1), (0, 1)])
def test_concurrency_is_clamped_both_ways(requested, expected):
    # Ask for a full roster so the roster-size cap does not interfere.
    _, _, concurrency = apply_swarm_options(
        AppConfig(), agents=100, max_concurrent=requested
    )
    assert concurrency == expected


def test_concurrency_never_exceeds_roster_size():
    _, agents, concurrency = apply_swarm_options(
        AppConfig(), agents=3, max_concurrent=16
    )
    assert agents == 3
    assert concurrency == 3


def test_budget_overrides_have_upper_bounds():
    cfg, _, _ = apply_swarm_options(
        AppConfig(), max_tokens=10**9, max_cost_usd=10_000.0
    )
    assert cfg.swarm.budget.max_tokens == SWARM_MAX_TOKENS_CEILING
    assert cfg.swarm.budget.max_cost_usd == SWARM_MAX_COST_CEILING


def test_budget_overrides_have_lower_bounds():
    cfg, _, _ = apply_swarm_options(AppConfig(), max_tokens=1, max_cost_usd=0.0)
    assert cfg.swarm.budget.max_tokens == 1000
    assert cfg.swarm.budget.max_cost_usd == 0.01


def test_no_overrides_uses_configured_defaults():
    cfg = AppConfig()
    cfg.swarm.default_agents = 12
    cfg.swarm.default_concurrent = 4
    _, agents, concurrency = apply_swarm_options(cfg)
    assert (agents, concurrency) == (12, 4)


def test_swarm_forces_cloud_analysis(monkeypatch):
    monkeypatch.setenv("AGENTARMOR_ANALYSIS_API_KEY", "key-from-env")
    cfg = AppConfig()
    cfg.detection.agentic.api_key = ""
    cfg, _, _ = apply_swarm_options(cfg)
    assert cfg.detection.analysis_mode == "cloud"
    assert cfg.detection.agentic.enabled is True
    assert cfg.detection.agentic.api_key == "key-from-env"


def test_explicit_key_is_not_overwritten_by_env(monkeypatch):
    monkeypatch.setenv("AGENTARMOR_ANALYSIS_API_KEY", "key-from-env")
    cfg = AppConfig()
    cfg.detection.agentic.api_key = "explicit"
    cfg, _, _ = apply_swarm_options(cfg)
    assert cfg.detection.agentic.api_key == "explicit"


def test_swarm_budget_drives_a_budget_governor():
    """SwarmBudgetConfig must be usable by the existing governor unchanged."""
    budget = SwarmBudgetConfig()
    governor = BudgetGovernor(budget)
    assert governor.allow_continue() is True
    governor.record_usage(input_tokens=budget.max_tokens, output_tokens=0)
    assert governor.allow_continue() is False
    assert governor.state.stopped is True


def test_swarm_budget_is_larger_than_the_redteam_budget():
    from agentarmor.core.config import RedTeamBudgetConfig

    assert SwarmBudgetConfig().max_tokens > RedTeamBudgetConfig().max_tokens
    assert SwarmBudgetConfig().max_cost_usd > RedTeamBudgetConfig().max_cost_usd


def test_redteam_budget_defaults_are_untouched():
    """Subclassing must not have changed the red-team ceiling."""
    from agentarmor.core.config import RedTeamBudgetConfig

    rt = RedTeamBudgetConfig()
    assert rt.max_tokens == 50_000
    assert rt.max_cost_usd == 2.0
