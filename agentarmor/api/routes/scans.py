"""Scan API routes for GUI and integrations."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agentarmor.core.config import apply_analysis_options, apply_endpoint_options, apply_multi_agent_redteam_options, apply_redteam_options, load_config, merge_cli_target
from agentarmor.core.models import Scan
from agentarmor.db.session import ScanRepository
from agentarmor.engines.router import validate_target
from agentarmor.services.scan_service import execute_scan

router = APIRouter(prefix="/v1/scans", tags=["scans"])

_config_path = Path(os.environ.get("AGENTARMOR_CONFIG", "AgentArmor.toml"))
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = ScanRepository(_app_config.database_url)


class ScanCreateRequest(BaseModel):
    target_type: str = "endpoint"
    url: str | None = None
    provider: str | None = None
    model: str | None = None
    agent: str | None = None
    agent_config: str | None = None
    mcp: str | None = None
    rag: str | None = None
    embedder: str | None = None
    auth_token: str | None = None
    analysis_mode: str = "offline"
    analysis_provider: str | None = None
    analysis_model: str | None = None
    analysis_api_key: str | None = None
    endpoint_profile: str | None = "auto"
    request_template: str | None = None
    response_path: str | None = None
    redteam_plugins: list[str] | None = None
    l0_enabled: bool | None = None
    max_variants_per_goal: int | None = None
    l0_suites: list[str] | None = None
    cloud_mutations_enabled: bool | None = None
    self_play_enabled: bool | None = None
    self_play_max_rounds: int | None = None
    self_play_stop_on_success: bool | None = None
    self_play_discovery_enabled: bool | None = None
    self_play_defender_enabled: bool | None = None
    scan_mode: str = "standard"
    redteam_max_rounds: int | None = None
    redteam_max_tokens: int | None = None
    redteam_max_cost_usd: float | None = None
    formats: list[str] = Field(default_factory=lambda: ["json", "html", "sarif"])
    config_path: str | None = None


def _build_config(body: ScanCreateRequest):
    cfg = load_config(
        Path(body.config_path) if body.config_path else _config_path
        if (body.config_path or _config_path.exists())
        else None
    )
    ttype = body.target_type.lower()
    if ttype == "endpoint":
        cfg = merge_cli_target(cfg, url=body.url)
    elif ttype == "provider":
        cfg = merge_cli_target(cfg, provider=body.provider, model=body.model)
    elif ttype == "local":
        cfg = merge_cli_target(cfg, model=body.model)
    elif ttype == "agent":
        cfg = merge_cli_target(cfg, agent=body.agent, agent_config=body.agent_config)
    elif ttype == "mcp":
        cfg = merge_cli_target(cfg, mcp=body.mcp)
    elif ttype == "rag":
        cfg = merge_cli_target(cfg, rag=body.rag, embedder=body.embedder)
    else:
        raise HTTPException(400, f"unsupported target_type: {body.target_type}")
    cfg = apply_analysis_options(
        cfg,
        analysis_mode=body.analysis_mode,
        analysis_provider=body.analysis_provider,
        analysis_model=body.analysis_model,
        analysis_api_key=body.analysis_api_key,
        auth_token=body.auth_token,
    )
    cfg = apply_endpoint_options(
        cfg,
        endpoint_profile=body.endpoint_profile,
        request_template=body.request_template,
        response_path=body.response_path,
        redteam_plugins=body.redteam_plugins,
    )
    cfg = apply_redteam_options(
        cfg,
        l0_enabled=body.l0_enabled,
        max_variants_per_goal=body.max_variants_per_goal,
        l0_suites=body.l0_suites,
        cloud_mutations_enabled=body.cloud_mutations_enabled,
        self_play_enabled=body.self_play_enabled,
        self_play_max_rounds=body.self_play_max_rounds,
        self_play_stop_on_success=body.self_play_stop_on_success,
        self_play_discovery_enabled=body.self_play_discovery_enabled,
        self_play_defender_enabled=body.self_play_defender_enabled,
    )
    cfg = apply_multi_agent_redteam_options(
        cfg,
        scan_mode=body.scan_mode,
        max_rounds=body.redteam_max_rounds,
        max_tokens=body.redteam_max_tokens,
        max_cost_usd=body.redteam_max_cost_usd,
    )
    if body.scan_mode == "multi_agent_redteam":
        if cfg.detection.analysis_mode != "cloud" or not cfg.detection.agentic.api_key:
            raise HTTPException(
                400,
                "multi_agent_redteam requires analysis_mode=cloud with a provider API key.",
            )
    validate_target(cfg)
    return cfg


@router.post("")
async def create_scan(body: ScanCreateRequest, background_tasks: BackgroundTasks) -> dict:
    _repo.ensure_schema()
    try:
        cfg = _build_config(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    scan = Scan(target=cfg.target)
    if body.scan_mode == "multi_agent_redteam":
        scan.metadata["scan_mode"] = "multi_agent_redteam"
    _repo.save_scan(scan)
    background_tasks.add_task(_run_scan_background, cfg, scan.id, body.formats)
    return {
        "scan_id": scan.id,
        "status": "started",
        "target_type": cfg.target.type.value,
        "analysis_mode": cfg.detection.analysis_mode,
    }


async def _run_scan_background(cfg, scan_id: str, formats: list[str]) -> None:
    cfg_copy = cfg.model_copy(deep=True)
    await execute_scan(cfg_copy, scan_id=scan_id, formats=formats)


@router.get("/{scan_id}")
def get_scan(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "scan not found")
    return scan.model_dump(mode="json")


@router.get("/{scan_id}/findings")
def get_scan_findings(scan_id: str) -> list[dict]:
    return [f.model_dump(mode="json") for f in _repo.list_findings(scan_id=scan_id)]


@router.get("/{scan_id}/reports")
def get_scan_reports(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "scan not found")
    return {"scan_id": scan_id, "reports": scan.metadata.get("reports", [])}
