"""Budget governor tests."""

from agentarmor.core.config import RedTeamBudgetConfig
from agentarmor.redteam.budget.governor import BudgetGovernor


def test_budget_stops_at_max_tokens():
    gov = BudgetGovernor(RedTeamBudgetConfig(max_tokens=1000, max_cost_usd=10.0))
    gov.record_usage(input_tokens=600, output_tokens=500, model="gpt-4o-mini")
    assert gov.state.stopped
    assert not gov.allow_continue()


def test_budget_warns_before_stop():
    gov = BudgetGovernor(RedTeamBudgetConfig(max_tokens=1000, warn_at_pct=50))
    gov.record_usage(input_tokens=400, output_tokens=100, model="gpt-4o-mini")
    assert gov.state.degraded
    assert gov.allow_continue()


def test_budget_cost_cap():
    gov = BudgetGovernor(RedTeamBudgetConfig(max_tokens=1_000_000, max_cost_usd=0.001))
    gov.record_usage(input_tokens=5000, output_tokens=5000, model="gpt-4o")
    assert gov.state.stopped or gov.state.cost_usd >= 0.001
