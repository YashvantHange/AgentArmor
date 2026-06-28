"""Web scan API routes."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agentarmor.api.report_files import MEDIA_TYPES, create_zip_archive, resolve_report_path, unlink_path

from agentarmor.core.config import apply_analysis_options, load_config
from agentarmor.core.models import ScanStatus
from agentarmor.webscan.auth import auth_session_manager, save_storage_state
from agentarmor.webscan.browser.pool import playwright_available
from agentarmor.webscan.models import AuthMode, ScanDepth
from agentarmor.webscan.orchestrator import WebScanOrchestrator, build_web_scan
from agentarmor.webscan.service import execute_web_scan
from agentarmor.db.session import ScanRepository

router = APIRouter(prefix="/v1/web-scans", tags=["web-scans"])

_config_path = Path(os.environ.get("AGENTARMOR_CONFIG", "AgentArmor.toml"))
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = ScanRepository(_app_config.database_url)


def _cloud_api_key_available(body: "WebScanCreateRequest") -> bool:
    if body.analysis_api_key:
        return True
    cfg = load_config(_config_path if _config_path.exists() else None)
    env_name = cfg.detection.agentic.api_key_env
    return bool(os.environ.get(env_name, ""))


def _validate_multi_agentic(body: "WebScanCreateRequest") -> WebScanCreateRequest:
    if body.scan_depth != ScanDepth.MULTI_AGENTIC.value:
        return body
    if body.analysis_mode != "cloud":
        if _cloud_api_key_available(body):
            return body.model_copy(update={"analysis_mode": "cloud"})
        raise HTTPException(
            400,
            "multi_agentic scan depth requires analysis_mode=cloud with a provider API key.",
        )
    if not _cloud_api_key_available(body):
        raise HTTPException(
            400,
            "multi_agentic requires analysis_api_key (not persisted; per-request only).",
        )
    return body


def _enforce_rate_limit(cfg) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    count = _repo.count_web_scans_since(since)
    limit = cfg.webscan.max_scans_per_day
    if count >= limit:
        raise HTTPException(
            429,
            f"Daily web scan limit reached ({limit} per 24h). Try again tomorrow or raise webscan.max_scans_per_day.",
        )


class WebDiscoverRequest(BaseModel):
    page_url: str


class WebPrepareSessionRequest(BaseModel):
    page_url: str
    owasp_filters: list[str] = Field(
        default_factory=lambda: ["LLM01", "LLM02", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09"]
    )


class WebScanContinueRequest(BaseModel):
    scan_depth: str = "standard"
    planner_enabled: bool = False
    owasp_filters: list[str] = Field(
        default_factory=lambda: ["LLM01", "LLM02", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09"]
    )
    analysis_mode: str = "offline"
    analysis_provider: str | None = None
    analysis_model: str | None = None
    analysis_api_key: str | None = None
    formats: list[str] = Field(default_factory=lambda: ["json", "html", "sarif"])


class WebScanCreateRequest(BaseModel):
    page_url: str
    scan_depth: str = "standard"
    auth_mode: str = "none"
    planner_enabled: bool = False
    owasp_filters: list[str] = Field(
        default_factory=lambda: ["LLM01", "LLM02", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09"]
    )
    analysis_mode: str = "offline"
    analysis_provider: str | None = None
    analysis_model: str | None = None
    analysis_api_key: str | None = None
    formats: list[str] = Field(default_factory=lambda: ["json", "html", "sarif"])


def _cfg_with_analysis(body: WebScanCreateRequest | WebScanContinueRequest):
    cfg = load_config(_config_path if _config_path.exists() else None)
    cfg = apply_analysis_options(
        cfg,
        analysis_mode=body.analysis_mode,
        analysis_provider=body.analysis_provider,
        analysis_model=body.analysis_model,
        analysis_api_key=body.analysis_api_key,
    )
    return cfg


def _check_webscan_ready() -> tuple[bool, str | None]:
    if not playwright_available():
        return False, "Playwright not installed. Run: pip install 'agentarmor[browser]' && agentarmor browser install"
    return True, None


def _parse_scan_depth(value: str) -> ScanDepth:
    if value in ("standard", "multi_agentic"):
        return ScanDepth(value)
    return ScanDepth.STANDARD


@router.get("/capabilities")
def webscan_capabilities() -> dict:
    ready, hint = _check_webscan_ready()
    return {
        "webscan_ready": ready,
        "hint": hint,
        "scan_depths": ["standard", "multi_agentic"],
        "auth_modes": ["none", "manual_session"],
        "multi_agentic_requires_cloud": True,
        "planner_requires_multi_agentic": True,
    }


@router.post("/discover")
async def discover_page(body: WebDiscoverRequest) -> dict:
    ready, hint = _check_webscan_ready()
    if not ready:
        raise HTTPException(503, hint or "web scan not ready")
    cfg = load_config(_config_path if _config_path.exists() else None)
    _repo.ensure_schema()
    runner = WebScanOrchestrator(cfg, _repo)
    try:
        result = await runner.discover_only(body.page_url)
    finally:
        await runner.close()
    if result.error and not result.widget:
        return {
            "ok": False,
            "error": result.error,
            "widget": None,
            "discovery": result.model_dump(mode="json"),
        }
    return {
        "ok": bool(result.widget),
        "error": result.error,
        "widget": result.widget.model_dump(mode="json") if result.widget else None,
        "framework": result.framework,
        "candidates": [c.model_dump(mode="json") for c in result.candidates],
        "capability_map": result.capability_map.model_dump(mode="json") if result.capability_map else None,
        "agent_risk": result.agent_risk.model_dump(mode="json") if result.agent_risk else None,
        "discovery": result.model_dump(mode="json"),
    }


@router.post("/prepare-session")
async def prepare_auth_session(body: WebPrepareSessionRequest) -> dict:
    ready, hint = _check_webscan_ready()
    if not ready:
        raise HTTPException(503, hint or "web scan not ready")

    cfg = load_config(_config_path if _config_path.exists() else None)
    _enforce_rate_limit(cfg)
    _repo.ensure_schema()

    scan = build_web_scan(
        body.page_url,
        owasp_filters=body.owasp_filters,
        auth_mode=AuthMode.MANUAL_SESSION,
    )
    scan.status = ScanStatus.AWAITING_AUTH
    _repo.save_scan(scan)

    try:
        await auth_session_manager.prepare(scan.id, body.page_url, cfg)
    except ValueError as exc:
        scan.status = ScanStatus.FAILED
        scan.metadata["error"] = str(exc)
        _repo.save_scan(scan)
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        scan.status = ScanStatus.FAILED
        scan.metadata["error"] = "failed to open login browser"
        _repo.save_scan(scan)
        raise HTTPException(500, "failed to open login browser") from exc

    return {
        "scan_id": scan.id,
        "status": ScanStatus.AWAITING_AUTH.value,
        "message": "Log in via the browser window, then call continue.",
    }


@router.post("/{scan_id}/continue")
async def continue_auth_session(
    scan_id: str,
    body: WebScanContinueRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    ready, hint = _check_webscan_ready()
    if not ready:
        raise HTTPException(503, hint or "web scan not ready")

    scan = _repo.get_scan(scan_id)
    if not scan or scan.status != ScanStatus.AWAITING_AUTH:
        raise HTTPException(404, "scan not found or not awaiting authentication")

    if body.planner_enabled and body.scan_depth != ScanDepth.MULTI_AGENTIC.value:
        raise HTTPException(400, "planner_enabled requires scan_depth=multi_agentic")

    body_for_validation = WebScanCreateRequest(
        page_url=scan.metadata.get("page_url", scan.target.url or ""),
        scan_depth=body.scan_depth,
        auth_mode=AuthMode.MANUAL_SESSION.value,
        planner_enabled=body.planner_enabled,
        owasp_filters=body.owasp_filters,
        analysis_mode=body.analysis_mode,
        analysis_provider=body.analysis_provider,
        analysis_model=body.analysis_model,
        analysis_api_key=body.analysis_api_key,
        formats=body.formats,
    )
    body_for_validation = _validate_multi_agentic(body_for_validation)

    cfg = _cfg_with_analysis(body_for_validation)
    try:
        storage_state = await auth_session_manager.finalize(scan_id)
    except KeyError as exc:
        raise HTTPException(409, "login browser session expired; call prepare-session again") from exc

    session_path = save_storage_state(
        scan_id,
        storage_state,
        ttl_hours=cfg.webscan.session_ttl_hours,
    )
    scan.metadata["auth_session_path"] = str(session_path)
    scan.metadata["scan_depth"] = body.scan_depth
    scan.metadata["planner_enabled"] = body.planner_enabled
    scan.metadata["owasp_filters"] = body.owasp_filters
    scan.metadata["analysis_mode"] = body.analysis_mode
    scan.status = ScanStatus.PENDING
    _repo.save_scan(scan)

    background_tasks.add_task(_run_web_scan_background, body_for_validation, scan_id)
    return {
        "scan_id": scan_id,
        "status": "started",
        "scan_kind": "web",
        "auth_mode": AuthMode.MANUAL_SESSION.value,
    }


@router.post("")
async def create_web_scan(body: WebScanCreateRequest, background_tasks: BackgroundTasks) -> dict:
    ready, hint = _check_webscan_ready()
    if not ready:
        raise HTTPException(503, hint or "web scan not ready")

    if body.auth_mode == AuthMode.MANUAL_SESSION.value:
        raise HTTPException(
            400,
            "manual_session requires POST /v1/web-scans/prepare-session then POST /v1/web-scans/{id}/continue.",
        )

    if body.planner_enabled and body.scan_depth != ScanDepth.MULTI_AGENTIC.value:
        raise HTTPException(400, "planner_enabled requires scan_depth=multi_agentic")

    cfg = load_config(_config_path if _config_path.exists() else None)
    _enforce_rate_limit(cfg)
    body = _validate_multi_agentic(body)

    _repo.ensure_schema()
    scan = build_web_scan(
        body.page_url,
        owasp_filters=body.owasp_filters,
        scan_depth=_parse_scan_depth(body.scan_depth),
        auth_mode=AuthMode(body.auth_mode) if body.auth_mode in ("none", "manual_session") else AuthMode.NONE,
        planner_enabled=body.planner_enabled,
    )
    scan.metadata["analysis_mode"] = body.analysis_mode
    _repo.save_scan(scan)
    background_tasks.add_task(_run_web_scan_background, body, scan.id)
    return {
        "scan_id": scan.id,
        "status": "started",
        "scan_kind": "web",
        "page_url": body.page_url,
    }


async def _run_web_scan_background(body: WebScanCreateRequest, scan_id: str) -> None:
    cfg = _cfg_with_analysis(body)
    scan = _repo.get_scan(scan_id)
    if not scan:
        return
    await execute_web_scan(cfg, scan, formats=body.formats)


@router.get("/{scan_id}")
def get_web_scan(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "scan not found")
    data = scan.model_dump(mode="json")
    data["scan_kind"] = scan.metadata.get("scan_kind", "web")
    return data


@router.get("/{scan_id}/findings")
def get_web_scan_findings(scan_id: str) -> list[dict]:
    return [f.model_dump(mode="json") for f in _repo.list_findings(scan_id=scan_id)]


@router.get("/{scan_id}/reports")
def get_web_scan_reports(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "scan not found")
    return {"scan_id": scan_id, "reports": scan.metadata.get("reports", [])}


@router.get("/{scan_id}/reports/download")
def download_web_scan_report(
    scan_id: str,
    format: str,
    background_tasks: BackgroundTasks,
) -> FileResponse:
    fmt = format.lower()
    if fmt not in MEDIA_TYPES:
        raise HTTPException(400, f"unsupported format: {format}")

    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "scan not found")

    output_dir = Path(_app_config.reporting.output_dir)

    if fmt == "zip":
        zip_path = create_zip_archive(scan, output_dir)
        background_tasks.add_task(unlink_path, zip_path)
        return FileResponse(
            zip_path,
            media_type=MEDIA_TYPES["zip"],
            filename=f"scan-{scan_id}-reports.zip",
        )

    file_path = resolve_report_path(scan, fmt, output_dir)
    return FileResponse(
        file_path,
        media_type=MEDIA_TYPES[fmt],
        filename=file_path.name,
    )
