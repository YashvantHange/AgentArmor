"""Scan API routes for GUI and integrations."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agentarmor.core.config import load_config, merge_cli_target
from agentarmor.core.events import event_bus
from agentarmor.core.models import Scan, TargetType
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
    _repo.save_scan(scan)
    background_tasks.add_task(_run_scan_background, cfg, scan.id, body.formats)
    return {"scan_id": scan.id, "status": "started", "target_type": cfg.target.type.value}


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
