"""Budget accounting under concurrency, and enrichment inside the ceiling."""

from __future__ import annotations

import asyncio

import pytest

from agentarmor.core.config import RedTeamBudgetConfig, SwarmBudgetConfig
from agentarmor.core.metering import UsageMeter, record_completion_usage
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.swarm.budget import AsyncBudgetGovernor, MemberMeter


def _governor(**overrides) -> AsyncBudgetGovernor:
    config = SwarmBudgetConfig(**overrides)
    return AsyncBudgetGovernor(config, estimate_tokens_per_call=2_000)


# --- the protocol contract --------------------------------------------------


def test_satisfies_the_usage_meter_protocol():
    """So it can be handed to judge_probe_verdict with no call-site change."""
    assert isinstance(_governor(), UsageMeter)
    assert isinstance(MemberMeter("sw-001", _governor()), UsageMeter)


def test_record_completion_usage_accepts_it():
    class _Usage:
        prompt_tokens = 40
        completion_tokens = 60

    class _Completion:
        usage = _Usage()
        _hidden_params = {"response_cost": 0.002}

    governor = _governor()
    record_completion_usage(governor, _Completion(), "gpt-4o-mini")
    assert governor.state.tokens_used == 100
    assert governor.total_cost_usd == pytest.approx(0.002)


# --- concurrency ------------------------------------------------------------


def test_concurrent_record_usage_loses_nothing():
    """record_usage is synchronous, so the loop cannot interleave inside it."""

    async def run():
        governor = _governor()

        async def writer():
            governor.record_usage(input_tokens=100, output_tokens=100)

        await asyncio.gather(*[writer() for _ in range(50)])
        return governor.state

    state = asyncio.run(run())
    assert state.tokens_used == 10_000
    assert state.calls == 50


def test_reservation_prevents_concurrent_overshoot():
    """The window the plain governor leaves open.

    allow_continue() then await lets N members each believe they have room. A
    reservation takes the check and the debit inside one lock hold.
    """

    async def run():
        governor = _governor(max_tokens=10_000)

        async def member():
            return await governor.try_reserve()

        results = await asyncio.gather(*[member() for _ in range(20)])
        granted = [r for r in results if r is not None]
        return granted, governor

    granted, governor = asyncio.run(run())
    assert len(granted) == 5, f"10_000 / 2_000 should grant 5, got {len(granted)}"
    assert governor.reserved_tokens == 10_000


def test_settling_a_reservation_frees_it():
    async def run():
        governor = _governor(max_tokens=4_000)
        first = await governor.try_reserve()
        second = await governor.try_reserve()
        blocked = await governor.try_reserve()
        await governor.settle(first)
        freed = await governor.try_reserve()
        return first, second, blocked, freed, governor.reserved_tokens

    first, second, blocked, freed, reserved = asyncio.run(run())
    assert first is not None and second is not None
    assert blocked is None, "the cap must hold while reservations are outstanding"
    assert freed is not None, "settling must release capacity"
    assert reserved == 4_000


def test_settling_twice_is_harmless():
    async def run():
        governor = _governor()
        reservation = await governor.try_reserve()
        await governor.settle(reservation)
        await governor.settle(reservation)
        await governor.settle(None)
        return governor.reserved_tokens

    assert asyncio.run(run()) == 0


def test_reservation_refused_once_the_budget_stops():
    async def run():
        governor = _governor(max_tokens=2_000)
        governor.record_usage(input_tokens=2_000, output_tokens=0)
        return await governor.try_reserve()

    assert asyncio.run(run()) is None


# --- per-member attribution -------------------------------------------------


def test_member_meters_attribute_spend_separately():
    """The first per-agent cost attribution in the codebase."""
    governor = _governor()
    first = MemberMeter("sw-001", governor)
    second = MemberMeter("sw-002", governor)

    first.record_usage(input_tokens=100, output_tokens=50, model="gpt-4o-mini")
    first.record_usage(input_tokens=100, output_tokens=50, model="gpt-4o-mini")
    second.record_usage(input_tokens=200, output_tokens=0, model="gpt-4o-mini")

    assert first.tokens == 300
    assert first.calls == 2
    assert second.tokens == 200
    assert second.calls == 1
    # The parent still sees the global total.
    assert governor.state.tokens_used == 500
    assert first.cost_usd > 0
    assert governor.total_cost_usd == pytest.approx(first.cost_usd + second.cost_usd)


def test_member_meter_reads_through_to_the_parent():
    governor = _governor(max_tokens=1_000)
    meter = MemberMeter("sw-001", governor)
    assert meter.allow_continue() is True
    meter.record_usage(input_tokens=1_000, output_tokens=0)
    assert meter.allow_continue() is False
    assert meter.state.stopped is True


# --- enrichment inside the ceiling ------------------------------------------


def test_enrichment_spend_counts_against_the_same_ceiling():
    """Capping the finding count limits how often enrichment runs, not its cost."""
    governor = _governor(max_tokens=1_000)
    governor.record_usage(input_tokens=400, output_tokens=0)
    assert governor.allow_continue() is True
    governor.record_enrichment_usage(input_tokens=600, output_tokens=0)
    assert governor.allow_continue() is False, "enrichment must be able to exhaust it"


def test_member_and_enrichment_costs_are_reported_separately():
    governor = _governor()
    governor.record_usage(input_tokens=1_000, output_tokens=0, litellm_cost=0.01)
    governor.record_enrichment_usage(input_tokens=500, output_tokens=0, litellm_cost=0.04)

    assert governor.member_cost_usd == pytest.approx(0.01)
    assert governor.enrichment_cost_usd == pytest.approx(0.04)
    assert governor.total_cost_usd == pytest.approx(0.05)
    assert governor.enrichment_tokens == 500
    assert governor.state.tokens_used == 1_500


def test_the_cost_ceiling_covers_enrichment():
    governor = _governor(max_cost_usd=0.10)
    governor.record_enrichment_usage(input_tokens=1, output_tokens=0, litellm_cost=0.20)
    assert governor.allow_continue() is False


# --- the enrichment chain accepts a meter -----------------------------------


def test_every_hop_of_the_enrichment_chain_takes_a_meter():
    """All three, not two: the middle hop is easy to miss."""
    import inspect

    from agentarmor.detection.agentic.coordinator import _llm_json, enrich_finding_agentic
    from agentarmor.reporting.enrichment import enrich_finding

    for fn in (enrich_finding, enrich_finding_agentic, _llm_json):
        assert "meter" in inspect.signature(fn).parameters, fn.__name__


def test_the_meter_parameter_is_optional_everywhere():
    """Existing callers pass three positional arguments and must keep working."""
    import inspect

    from agentarmor.detection.agentic.coordinator import _llm_json, enrich_finding_agentic
    from agentarmor.reporting.enrichment import enrich_finding

    for fn in (enrich_finding, enrich_finding_agentic, _llm_json):
        assert inspect.signature(fn).parameters["meter"].default is None, fn.__name__


# --- the plain governor is untouched ----------------------------------------


def test_plain_governor_semantics_are_unchanged():
    """Four test files and the whole red-team path depend on these exactly."""
    governor = BudgetGovernor(RedTeamBudgetConfig())
    assert governor.allow_continue() is True
    governor.record_usage(input_tokens=50_000, output_tokens=0)
    assert governor.allow_continue() is False
    assert governor.state.stopped is True
    # Recording past the cap must still not raise: governor.py:56-57 is a no-op.
    governor.record_usage(input_tokens=1, output_tokens=1)
    assert governor.state.stopped is True


def test_warn_threshold_still_degrades():
    governor = _governor(max_tokens=1_000, warn_at_pct=80.0)
    governor.record_usage(input_tokens=800, output_tokens=0)
    assert governor.degraded is True
    assert governor.allow_continue() is True, "degraded is not stopped"


def test_swarm_governor_wraps_without_subclassing_the_original():
    assert not isinstance(_governor(), BudgetGovernor)
    assert isinstance(_governor().state.tokens_used, int)
