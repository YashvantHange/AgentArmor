"""Continuous monitoring models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MonitorSchedule(BaseModel):
    id: str
    name: str
    target_type: str
    target_config: dict = Field(default_factory=dict)
    cron: str = "daily"  # daily | hourly | weekly | manual
    enabled: bool = True
    last_run_at: str | None = None
    last_scan_id: str | None = None
    last_finding_count: int = 0
    drift_detected: bool = False


class MonitorRunResult(BaseModel):
    schedule_id: str
    scan_id: str
    finding_count: int
    new_findings: int
    regressed: bool
