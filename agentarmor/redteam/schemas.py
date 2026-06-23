"""Pydantic models for multi-agent red team."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TargetProfile(BaseModel):
    """Unified capability profile for attack-graph planning."""

    tool_access: bool = False
    rag: bool = False
    memory: bool = False
    mcp: bool = False
    a2a: bool = False
    email_tool: bool = False
    framework: str | None = None
    tools: list[str] = Field(default_factory=list)


class AttackPathNode(BaseModel):
    node_id: str
    name: str
    owasp: list[str] = Field(default_factory=list)
    agent: str = "generic"
    priority: float = 0.5


class AttackPath(BaseModel):
    path_id: str
    name: str
    nodes: list[AttackPathNode] = Field(default_factory=list)
    priority_rank: int = 99
    rationale: str = ""


class AttackPlan(BaseModel):
    path_id: str
    next_node: str
    strategy: str = "direct"
    rationale: str = ""
    estimated_rounds: int = 1


class AttackPrompt(BaseModel):
    probe_id: str
    name: str
    prompt: str
    owasp: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    mutations_applied: list[str] = Field(default_factory=list)
    multi_turn: list[str] | None = None
    attack_path: str = ""
    node_id: str = ""


class BudgetState(BaseModel):
    tokens_used: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    degraded: bool = False
    stopped: bool = False
    stop_reason: str | None = None


class RedTeamVerdict(BaseModel):
    vulnerable: bool = False
    confidence_score: float = 0.0
    reproducibility_score: float = 0.0
    impact_score: str = "low"
    impact_rationale: str = ""
    evidence_quotes: list[str] = Field(default_factory=list)
    rationale: str = ""
    attack_path: str = ""
    node_id: str = ""
    owasp: list[str] = Field(default_factory=list)


class RoundRecord(BaseModel):
    round: int
    plan: AttackPlan
    attack: AttackPrompt
    response_excerpt: str = ""
    verdict: RedTeamVerdict
    probe_error: str | None = None


class RedTeamTrace(BaseModel):
    profile: TargetProfile
    paths: list[AttackPath] = Field(default_factory=list)
    rounds: list[RoundRecord] = Field(default_factory=list)
    budget: BudgetState = Field(default_factory=BudgetState)
    path_outcomes: dict[str, list[bool]] = Field(default_factory=dict)


class TargetCapabilities(BaseModel):
    """Optional user-declared or discovered capabilities for API scans."""

    rag: bool = False
    memory: bool = False
    mcp: bool = False
    a2a: bool = False
    tools: list[str] = Field(default_factory=list)
