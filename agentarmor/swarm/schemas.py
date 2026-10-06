"""Pydantic models for cooperative swarm runs."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field

from agentarmor.redteam.schemas import BudgetState

FactKind = Literal[
    "secret",
    "system_prompt",
    "tool_name",
    "pii",
    "policy",
    "refusal_style",
    "capability",
    "bypass",
    # Catch-all for a real discovery that fits none of the above, such as
    # "responses diverge above temperature 1". Evidence, but not a capability,
    # policy, or bypass.
    "observation",
]

# How much a fact can be trusted to steer other members:
#   verified - a detection rule or structured pattern matched
#   inferred - an LLM judge quoted it
#   observed - raw target text, lowest trust
Provenance = Literal["observed", "inferred", "verified"]

Strategy = Literal["direct", "mutation_retry", "crescendo"]

_WHITESPACE = re.compile(r"\s+")


def normalize_fact_value(value: str) -> str:
    """Collapse a fact value for hashing so trivial spacing differs don't dedupe."""
    return _WHITESPACE.sub(" ", value).strip().lower()


def fact_id_for(kind: str, value: str) -> str:
    digest = hashlib.sha1(f"{kind}|{normalize_fact_value(value)}".encode("utf-8"))
    return digest.hexdigest()[:12]


class SwarmGoal(BaseModel):
    """A preset goal a swarm can pursue. There is no free-text goal by design."""

    id: str
    name: str
    description: str
    owasp: list[str] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list)
    mutations: list[str] = Field(default_factory=list)


class SwarmCoverage(BaseModel):
    """What a roster actually spans.

    Surfaced in the API, the CLI and the GUI so an agent count is never shown on
    its own. A 100-member roster against a bare endpoint covers only the
    unconditional baseline nodes, so most of its breadth is persona and strategy
    variation rather than new attack classes. Saying so is the honest framing.
    """

    agents: int = 0
    attack_paths: int = 0
    nodes: int = 0
    personas: int = 0
    strategies: int = 0
    concurrency: int = 0

    def summary_line(self) -> str:
        return (
            f"Agents {self.agents} | Attack paths {self.attack_paths} | "
            f"Personas {self.personas} | Strategies {self.strategies} | "
            f"Concurrency {self.concurrency}"
        )


class SwarmMember(BaseModel):
    """One roster slot: the tuple that makes a member distinct.

    Specialization is data, not a class. The 13 red-team agents already differ
    only by agent id (system prompt), skill (seeds, mutations, judge rubric) and
    strategy, so crossing those with a persona yields far more distinct members
    than the roster ceiling needs, without a single new YAML file.
    """

    member_id: str
    base_agent_id: str
    skill_id: str
    node_id: str
    path_id: str
    persona_id: str
    subgoal: str = ""
    strategy: Strategy = "direct"
    mutation_bias: list[str] = Field(default_factory=list)
    temperature: float = 0.4
    owasp: list[str] = Field(default_factory=list)
    priority: float = 0.5


class Fact(BaseModel):
    """A deduplicated observation about the target, shared between members.

    ``value`` is text captured from the target. It is sanitized on publish and
    always rendered to a member inside an untrusted-data envelope: a swarm feeds
    one member's observations to the next, so an injection in a target response
    would otherwise reach another agent's context.
    """

    fact_id: str
    kind: FactKind
    value: str
    source_member_id: str
    node_id: str = ""
    owasp: list[str] = Field(default_factory=list)
    provenance: Provenance = "observed"
    confidence: float = 0.5
    wave: int = 0
    # Incremented when another member reports the same fact. Independent
    # corroboration is a signal worth keeping, and it costs nothing to track.
    hits: int = 1
    # True when the value looks like an instruction rather than evidence. Kept
    # for the report, withheld from the briefs handed to other members.
    quarantined: bool = False


class MemberRecord(BaseModel):
    """Per-member outcome, including the first per-agent cost attribution."""

    member_id: str
    node_id: str
    path_id: str
    persona_id: str
    skill_id: str
    strategy: str = "direct"
    wave: int = 0
    vulnerable: bool = False
    decision: str = ""
    confidence: float = 0.0
    tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    attempts: int = 1
    latency_ms: float = 0.0
    facts_published: int = 0
    error: str | None = None


class SwarmSummary(BaseModel):
    """Headline numbers for the report and the progress UI."""

    goal_id: str
    goal_name: str = ""
    agents_requested: int = 0
    agents: int = 0
    max_concurrent: int = 0
    completed: int = 0
    failed: int = 0
    vulnerable: int = 0
    findings: int = 0
    waves: int = 0
    blackboard_facts: int = 0
    # Member generation and judging versus finding enrichment, tracked
    # separately so the cost ceiling covers both instead of only the first.
    member_cost_usd: float = 0.0
    enrichment_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    tokens_used: int = 0
    degraded: bool = False
    stopped: bool = False
    stop_reason: str = ""
    cancelled: bool = False
    coverage: SwarmCoverage = Field(default_factory=SwarmCoverage)


class SwarmTrace(BaseModel):
    """Append-only run log, persisted into ``scan.metadata``.

    Written only by the coordinator coroutine. Member coroutines return outcomes
    and never touch it, which is what keeps it single-writer under concurrency.
    """

    goal_id: str
    agents_requested: int = 0
    agents: int = 0
    max_concurrent: int = 0
    coverage: SwarmCoverage = Field(default_factory=SwarmCoverage)
    roster: list[SwarmMember] = Field(default_factory=list)
    members: list[MemberRecord] = Field(default_factory=list)
    node_outcomes: dict[str, list[bool]] = Field(default_factory=dict)
    waves: int = 0
    budget: BudgetState = Field(default_factory=BudgetState)
