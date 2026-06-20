"""Benchmark API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agentarmor.benchmark.config import BenchmarkTarget
from agentarmor.benchmark.runner import run_benchmark
from agentarmor.core.config import load_config
from agentarmor.db.benchmark_session import BenchmarkRepository

router = APIRouter(prefix="/v1/benchmarks", tags=["benchmarks"])

_config_path = Path("AgentArmor.toml")
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = BenchmarkRepository(_app_config.database_url)


class BenchmarkTargetRequest(BaseModel):
    label: str | None = None
    type: str = "provider"
    provider: str | None = None
    model: str | None = None


class BenchmarkCreateRequest(BaseModel):
    suite: str = "owasp"
    targets: list[BenchmarkTargetRequest] = Field(default_factory=list)


@router.post("")
async def create_benchmark(body: BenchmarkCreateRequest, background_tasks: BackgroundTasks) -> dict:
    _repo.ensure_schema()
    if not body.targets:
        raise HTTPException(400, "at least one target is required")
    targets = [
        BenchmarkTarget(
            label=t.label or t.provider or t.model or t.type,
            type=t.type,
            provider=t.provider,
            model=t.model,
        )
        for t in body.targets
    ]
    from agentarmor.benchmark.models import BenchmarkRun, BenchmarkStatus

    placeholder = BenchmarkRun(
        suite_id=body.suite,
        suite_name=body.suite,
        status=BenchmarkStatus.PENDING,
        metadata={"targets": [t.model_dump() for t in targets]},
    )
    _repo.save_run(placeholder)

    background_tasks.add_task(_run_benchmark_bg, body.suite, targets, placeholder.id)
    return {"benchmark_id": placeholder.id, "status": "started"}


async def _run_benchmark_bg(suite: str, targets: list[BenchmarkTarget], run_id: str) -> None:
    completed = await run_benchmark(_app_config, suite, targets)
    completed.id = run_id
    _repo.save_run(completed)


@router.get("/{benchmark_id}")
def get_benchmark(benchmark_id: str) -> dict:
    _repo.ensure_schema()
    run = _repo.get_run(benchmark_id)
    if not run:
        raise HTTPException(404, "benchmark not found")
    return run.model_dump(mode="json")
