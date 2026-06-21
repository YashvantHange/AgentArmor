"""Tools comparison benchmark models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ToolScore(BaseModel):
    tool: str
    detection_rate: float | None = None
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    scenarios_tested: int = 0
    status: ToolStatus = ToolStatus.COMPLETED
    detail: str = ""


class ToolsComparisonRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    suite: str
    targets: list[str] = Field(default_factory=list)
    tool_scores: list[ToolScore] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def leader(self) -> str | None:
        ranked = [s for s in self.tool_scores if s.detection_rate is not None]
        if not ranked:
            return None
        return max(ranked, key=lambda s: s.detection_rate or 0.0).tool
