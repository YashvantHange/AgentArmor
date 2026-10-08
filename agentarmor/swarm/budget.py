"""Budget accounting for concurrent members.

``BudgetGovernor`` is correct for the sequential red-team loop and is not touched
here: four test files and the whole red-team path depend on its exact semantics.

The race it has under concurrency is **not** inside ``record_usage``. That method
is synchronous, and a synchronous method runs to completion without the event loop
preempting it, so its read-modify-write is already atomic. The window is between
``allow_continue()`` returning True and the ``await`` that follows it. With N
members in flight, all N can pass the check before any of them records usage, and
the budget overshoots by up to N calls.

``AsyncBudgetGovernor`` closes exactly that window with a reservation: the check
and the debit happen inside one lock hold, so budget is committed before the
await. Worst-case overshoot drops from "N times the actual cost" to the difference
between estimate and actual on at most ``max_concurrent`` in-flight calls.

It also tracks enrichment spend separately. Finding enrichment runs a five-agent
pipeline that bypasses the governor entirely, so capping the finding *count* limits
how often that happens without limiting what it costs. Both streams are summed
into one ceiling, which is what makes the configured cost cap mean something.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agentarmor.core.config import RedTeamBudgetConfig
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import BudgetState

# Used when a reservation is taken without a caller-supplied size. One member does
# roughly a generate plus a judge call; this is the per-call share.
DEFAULT_ESTIMATE_TOKENS = 2_000


@dataclass
class Reservation:
    """A claim on budget, held across an await and settled afterwards."""

    tokens: int
    settled: bool = False


class AsyncBudgetGovernor:
    """Lock-guarded, reservation-based budget for concurrent writers.

    Structurally satisfies ``core.metering.UsageMeter``, so it can be handed
    straight to ``judge_probe_verdict(..., meter=...)`` and
    ``record_completion_usage`` with no call-site change.
    """

    def __init__(
        self,
        config: RedTeamBudgetConfig,
        *,
        estimate_tokens_per_call: int = DEFAULT_ESTIMATE_TOKENS,
    ) -> None:
        self._inner = BudgetGovernor(config)
        self._lock = asyncio.Lock()
        self._estimate = max(1, estimate_tokens_per_call)
        self._reserved_tokens = 0
        self._member_cost_usd = 0.0
        self._enrichment_cost_usd = 0.0
        self._enrichment_tokens = 0

    # -- reservations -------------------------------------------------------

    async def try_reserve(self, *, tokens: int | None = None) -> Reservation | None:
        """Claim budget before issuing a call, or return None if there is none left.

        The check and the debit are one atomic section, which is the entire point:
        doing them separately is what lets N concurrent members each believe they
        have room.
        """
        want = max(1, tokens or self._estimate)
        async with self._lock:
            if not self._inner.allow_continue():
                return None
            projected = self._inner.state.tokens_used + self._reserved_tokens + want
            if projected > self._inner.config.max_tokens:
                return None
            self._reserved_tokens += want
            return Reservation(tokens=want)

    async def settle(self, reservation: Reservation | None) -> None:
        """Release a reservation once the real usage has been recorded."""
        if reservation is None or reservation.settled:
            return
        async with self._lock:
            reservation.settled = True
            self._reserved_tokens = max(0, self._reserved_tokens - reservation.tokens)

    # -- UsageMeter ---------------------------------------------------------

    def record_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None:
        """Record real usage.

        Synchronous and lock-free on purpose: it matches the ``UsageMeter``
        signature exactly, and without an await inside it the event loop cannot
        interleave another writer partway through.
        """
        before = self._inner.state.cost_usd
        self._inner.record_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            litellm_cost=litellm_cost,
        )
        self._member_cost_usd += self._inner.state.cost_usd - before

    def record_enrichment_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None:
        """Record finding-enrichment usage against the same ceiling.

        Enrichment runs a five-agent pipeline outside the governor. Counted here it
        can exhaust the budget like any other spend, which is what the configured
        cost cap has to mean to be a cap at all.
        """
        before_cost = self._inner.state.cost_usd
        before_tokens = self._inner.state.tokens_used
        self._inner.record_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            litellm_cost=litellm_cost,
        )
        self._enrichment_cost_usd += self._inner.state.cost_usd - before_cost
        self._enrichment_tokens += self._inner.state.tokens_used - before_tokens

    # -- read-through -------------------------------------------------------

    def allow_continue(self) -> bool:
        return self._inner.allow_continue()

    def should_degrade(self) -> bool:
        return self._inner.should_degrade()

    @property
    def state(self) -> BudgetState:
        return self._inner.state

    @property
    def config(self) -> RedTeamBudgetConfig:
        return self._inner.config

    @property
    def degraded(self) -> bool:
        return self._inner.state.degraded

    @property
    def member_cost_usd(self) -> float:
        return round(self._member_cost_usd, 6)

    @property
    def enrichment_cost_usd(self) -> float:
        return round(self._enrichment_cost_usd, 6)

    @property
    def enrichment_tokens(self) -> int:
        return self._enrichment_tokens

    @property
    def total_cost_usd(self) -> float:
        return round(self._inner.state.cost_usd, 6)

    @property
    def reserved_tokens(self) -> int:
        return self._reserved_tokens


@dataclass
class MemberMeter:
    """Per-member view onto the swarm budget.

    The first per-agent cost attribution in the codebase: the governor has always
    been global with no way to say which agent spent what. Satisfies ``UsageMeter``
    and delegates every record to the parent, so the global ceiling still applies.
    """

    member_id: str
    parent: AsyncBudgetGovernor
    tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    attempts: int = 0
    _parent_cost_at_start: float = field(default=0.0, init=False)

    def record_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None:
        before = self.parent.state.cost_usd
        self.parent.record_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            litellm_cost=litellm_cost,
        )
        self.tokens += input_tokens + output_tokens
        self.calls += 1
        self.cost_usd = round(self.cost_usd + (self.parent.state.cost_usd - before), 6)

    def allow_continue(self) -> bool:
        """Present so a MemberMeter can stand in wherever a governor is expected."""
        return self.parent.allow_continue()

    @property
    def state(self) -> BudgetState:
        return self.parent.state

    @property
    def degraded(self) -> bool:
        return self.parent.degraded
