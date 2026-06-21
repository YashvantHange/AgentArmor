"""Monitoring schedule API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agentarmor.core.config import load_config
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.monitoring.runner import run_scheduled_scan

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])

_config_path = Path("AgentArmor.toml")
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = MonitorRepository(_app_config.database_url)


class ScheduleCreateRequest(BaseModel):
    name: str
    target_type: str = "endpoint"
    target_config: dict = Field(default_factory=dict)
    cron: str = "daily"


@router.get("/schedules")
def list_schedules() -> list[dict]:
    _repo.ensure_schema()
    return [s.model_dump(mode="json") for s in _repo.list_schedules()]


@router.post("/schedules")
def create_schedule(body: ScheduleCreateRequest) -> dict:
    _repo.ensure_schema()
    schedule = _repo.create_schedule(
        name=body.name,
        target_type=body.target_type,
        target_config=body.target_config,
        cron=body.cron,
    )
    return schedule.model_dump(mode="json")


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str) -> dict:
    _repo.ensure_schema()
    if _repo.delete_schedule(schedule_id):
        return {"status": "deleted", "id": schedule_id}
    raise HTTPException(404, "schedule not found")


@router.post("/schedules/{schedule_id}/run")
async def run_schedule(schedule_id: str, background_tasks: BackgroundTasks) -> dict:
    _repo.ensure_schema()
    if not _repo.get_schedule(schedule_id):
        raise HTTPException(404, "schedule not found")
    background_tasks.add_task(_run_schedule_bg, schedule_id)
    return {"status": "started", "schedule_id": schedule_id}


async def _run_schedule_bg(schedule_id: str) -> None:
    await run_scheduled_scan(schedule_id, repo=_repo, config=_app_config)
