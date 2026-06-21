"""Domain models for scans, probes, and findings."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Decision(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class TargetType(str, Enum):
    ENDPOINT = "endpoint"
    PROVIDER = "provider"
    LOCAL = "local"
    AGENT = "agent"
    MCP = "mcp"
    RAG = "rag"


class Target(BaseModel):
    type: TargetType = TargetType.ENDPOINT
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    model: str | None = "gpt-3.5-turbo"
    provider: str | None = None
    agent_framework: str | None = None
    agent_config: str | None = None
    mcp_target: str | None = None
    mcp_transport: str = "stdio"
    rag_corpus: str | None = None
    embedder: str = "bge"


class ProbeRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7


class ProbeResponse(BaseModel):
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)
    status_code: int = 200


class ProbeResult(BaseModel):
    probe_id: str
    probe_name: str
    owasp: list[str] = Field(default_factory=list)
    request: ProbeRequest
    response: ProbeResponse
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    error: str | None = None


class DetectionResult(BaseModel):
    risk_score: float = 0.0
    severity: Severity = Severity.INFO
    decision: Decision = Decision.PASS
    categories: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    layers: dict[str, Any] = Field(default_factory=dict)


class AttackStep(BaseModel):
    step: str
    probe_id: str
    mutated_from: str | None = None
    response_hash: str | None = None
    evidence: str | None = None


class AttackTree(BaseModel):
    attack_goal: str
    attack_tree_id: str = Field(default_factory=lambda: str(uuid4()))
    path: list[AttackStep] = Field(default_factory=list)
    successful: bool = False


class RiskAssessment(BaseModel):
    risk_score: int = 0
    confidence: float = 0.0
    exploitability: float = 0.0
    impact: Severity = Severity.INFO
    reproducibility: float = 0.0


class EvidenceGraph(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    scan_id: str
    probe_id: str
    probe_name: str
    owasp: list[str] = Field(default_factory=list)
    title: str
    description: str = ""
    severity: Severity
    decision: Decision
    risk_score: float
    evidence: list[str] = Field(default_factory=list)
    request_summary: str = ""
    response_excerpt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    risk_assessment: RiskAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Scan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    target: Target
    status: ScanStatus = ScanStatus.PENDING
    probe_count: int = 0
    finding_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanEvent(BaseModel):
    event: str
    scan_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
