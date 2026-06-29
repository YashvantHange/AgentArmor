"""FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from agentarmor import __version__
from agentarmor.api.routes.benchmarks import router as benchmarks_router
from agentarmor.api.routes.datasets import router as datasets_router
from agentarmor.api.routes.marketplace import router as marketplace_router
from agentarmor.api.routes.monitoring import router as monitoring_router
from agentarmor.api.routes.scans import router as scans_router
from agentarmor.api.routes.settings import router as settings_router
from agentarmor.api.routes.targets import router as targets_router
from agentarmor.api.routes.web_scans import router as web_scans_router
from agentarmor.core.config import load_config
from agentarmor.core.events import event_bus
from agentarmor.db.benchmark_session import BenchmarkRepository
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.db.session import ScanRepository
from agentarmor.detection.api.routes import router as detection_router
from agentarmor.monitoring.scheduler import MonitoringScheduler
from agentarmor.webscan.browser.pool import playwright_available

_config_path = Path(os.environ.get("AGENTARMOR_CONFIG", "AgentArmor.toml"))
_app_config = load_config(_config_path if _config_path.exists() else None)

if os.environ.get("AGENTARMOR_MODEL_DIR"):
    _app_config.detection.model_dir = os.environ["AGENTARMOR_MODEL_DIR"]
if os.environ.get("AGENTARMOR_DATA_DIR"):
    data_dir = Path(os.environ["AGENTARMOR_DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    _app_config.database_url = f"sqlite:///{data_dir / 'agentarmor.db'}"
    _app_config.reporting.output_dir = str(data_dir / "reports")

_repo = ScanRepository(_app_config.database_url)
_benchmark_repo = BenchmarkRepository(_app_config.database_url)
_monitor_repo = MonitorRepository(_app_config.database_url)
_scheduler: MonitoringScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    _repo.ensure_schema()
    _benchmark_repo.ensure_schema()
    _monitor_repo.ensure_schema()
    _scheduler = MonitoringScheduler(_monitor_repo, _app_config)
    _scheduler.start()
    yield
    if _scheduler:
        await _scheduler.stop()


app = FastAPI(title="AgentArmor", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(detection_router)
app.include_router(benchmarks_router)
app.include_router(marketplace_router)
app.include_router(monitoring_router)
app.include_router(datasets_router)
app.include_router(scans_router)
app.include_router(settings_router)
app.include_router(targets_router)
app.include_router(web_scans_router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    ready = playwright_available()
    return {
        "status": "ok",
        "version": __version__,
        "webscan_ready": ready,
    }


@app.get("/v1/findings")
def list_findings(scan_id: str | None = None, grouped: bool = True) -> list[dict]:
    from agentarmor.reporting.finding_cluster import grouped_findings_api

    findings = _repo.list_findings(scan_id=scan_id)
    if grouped:
        return grouped_findings_api(findings)
    return [f.model_dump(mode="json") for f in findings]


_SSE_HEARTBEAT_INTERVAL_S = 30.0


@app.get("/v1/scans/{scan_id}/events")
async def scan_events(scan_id: str):
    queue = event_bus.subscribe(scan_id)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_INTERVAL_S)
                except asyncio.TimeoutError:
                    yield {
                        "event": "scan.heartbeat",
                        "data": json.dumps({"scan_id": scan_id}),
                    }
                    continue
                yield {"event": event.event, "data": json.dumps(event.data, default=str)}
                if event.event == "scan.completed":
                    break
        finally:
            event_bus.unsubscribe(scan_id, queue)

    return EventSourceResponse(generator())
