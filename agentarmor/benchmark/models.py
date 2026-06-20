"""Benchmark domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class BenchmarkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkTarget(BaseModel):
    label: str
    type: str  # provider | local
    provider: str | None = None
    model: str | None = None


class ProbeBenchmarkResult(BaseModel):
    probe_id: str
    category_id: str
    decision: str
    risk_score: float
    severity: str


class CategoryScore(BaseModel):
    category_id: str
    category_name: str
    pass_rate: float
    mean_risk: float
    probe_count: int
    passed: int


class ModelScore(BaseModel):
    target: BenchmarkTarget
    pass_rate: float
    risk_score: float
    rank: int = 0
    category_scores: list[CategoryScore] = Field(default_factory=list)
    probe_results: list[ProbeBenchmarkResult] = Field(default_factory=list)


class BenchmarkRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    suite_id: str
    suite_name: str
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    model_scores: list[ModelScore] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def created_at(self) -> datetime:
        return self.started_at or datetime.now(timezone.utc)
