"""FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sse_starlette.sse import EventSourceResponse

from agentarmor import __version__
from agentarmor.api.routes.benchmarks import router as benchmarks_router
from agentarmor.api.routes.datasets import router as datasets_router
from agentarmor.api.routes.marketplace import router as marketplace_router
from agentarmor.api.routes.monitoring import router as monitoring_router
from agentarmor.api.routes.scans import router as scans_router
from agentarmor.api.routes.swarms import router as swarms_router
from agentarmor.api.routes.settings import router as settings_router
from agentarmor.api.routes.targets import router as targets_router
from agentarmor.api.routes.web_scans import router as web_scans_router
from agentarmor.core.config import load_config
from agentarmor.core.events import event_bus
from agentarmor.core.jobs import job_registry
from agentarmor.engines.endpoint.pool import aclose_all
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
    # Order matters: cancel tracked jobs before closing the shared HTTP clients,
    # so an in-flight swarm member is cancelled rather than failing on a closed
    # transport on its way out.
    await job_registry.drain()
    await aclose_all()


app = FastAPI(title="AgentArmor", version=__version__, lifespan=lifespan)
# Origins the desktop app and local development actually use. Everything else is
# refused.
#
# allow_origins=["*"] with allow_credentials=True was worse than it looked:
# Starlette sets preflight_explicit_allow_origin = not allow_all_origins or
# allow_credentials, so it echoed the *requesting* origin instead of "*". A
# preflight from https://evil.example.com came back with
# access-control-allow-origin: https://evil.example.com and
# access-control-allow-credentials: true - meaning any page the user had open could
# drive this API, which since 1.5.0 includes launching a hundred-agent swarm at a
# host of its choosing.
#
# The port list is explicit rather than a wildcard. Allowing localhost on *any*
# port makes every other local web server a trusted origin - a dev server, a
# notebook, a tool installed by an npm postinstall - and any of those could then
# drive this API from a page the user opened in it.
VITE_DEV_PORT = 1420  # tauri.conf.json build.devUrl
DEFAULT_API_PORT = 8787


def _local_ports() -> set[int]:
    """The ports a browser may legitimately be serving the GUI from."""
    ports = {VITE_DEV_PORT, DEFAULT_API_PORT}
    try:
        configured = urlparse(_app_config.api_url).port
    except (ValueError, AttributeError):
        configured = None
    if configured:
        ports.add(configured)
    return ports


def allowed_origin_regex() -> str:
    """The origin allowlist, overridable for an unusual packaging or host.

    Set AGENTARMOR_ALLOW_ORIGIN_REGEX to replace it. Set it to ".*" to restore the
    previous allow-anything behaviour, deliberately and visibly.
    """
    override = os.environ.get("AGENTARMOR_ALLOW_ORIGIN_REGEX")
    if override:
        return override
    ports = "|".join(str(port) for port in sorted(_local_ports()))
    return (
        r"^(?:"
        r"tauri://localhost"  # Tauri v2 on macOS and Linux
        r"|https?://tauri\.localhost"  # Tauri v2 on Windows
        rf"|https?://(?:localhost|127\.0\.0\.1)(?::(?:{ports}))?"
        r")$"
    )


# Host-header allowlist, which is what actually stops DNS rebinding. CORS alone does
# not: an attacker can point evil.example.com at 127.0.0.1, and while the Origin
# check refuses the resulting cross-origin request, nothing was verifying that the
# request was addressed to this service at all. The server binds loopback by default,
# so a request arriving as Host: evil.example.com is never legitimate.
DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "::1", "tauri.localhost", "testserver"]


def allowed_hosts() -> list[str]:
    """Hosts this API answers to. AGENTARMOR_ALLOWED_HOSTS overrides, comma-separated.

    Override it when deliberately binding something other than loopback; "*"
    disables the check.
    """
    override = os.environ.get("AGENTARMOR_ALLOWED_HOSTS", "").strip()
    if override:
        return [host.strip() for host in override.split(",") if host.strip()]
    return list(DEFAULT_ALLOWED_HOSTS)


# Ordering matters: the host check runs before CORS, so a rebound request is refused
# outright rather than being evaluated for an origin it was never going to pass.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=allowed_origin_regex(),
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
app.include_router(swarms_router)
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
