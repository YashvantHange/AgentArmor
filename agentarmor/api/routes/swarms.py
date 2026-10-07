"""Swarm endpoints.

Only four routes, because a swarm is a scan: SSE, findings and report download all
work through the existing ``/v1/scans/{id}/*`` endpoints thanks to the
``scan_kind`` discriminator. Web scans duplicated those three; there is no reason
to compound that.

Launching goes through ``JobRegistry`` rather than Starlette ``BackgroundTasks``.
A background task keeps no handle, so it cannot be cancelled, counted against a
concurrency limit, or drained at shutdown - all three of which a hundred-member run
against a live target needs.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentarmor.core.config import (
    AppConfig,
    apply_analysis_options,
    apply_endpoint_options,
    apply_swarm_options,
    ensure_analysis_ready,
    load_config,
    merge_cli_target,
)
from agentarmor.core.jobs import job_registry
from agentarmor.db.session import ScanRepository
from agentarmor.engines.router import validate_target
from agentarmor.services.swarm_service import build_swarm_scan, execute_swarm
from agentarmor.swarm.goals import get_swarm_goal, list_swarm_goal_ids, list_swarm_goals

router = APIRouter(prefix="/v1/swarms", tags=["swarms"])

_log = logging.getLogger(__name__)
_config_path = Path(os.environ.get("AGENTARMOR_CONFIG", "AgentArmor.toml"))
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = ScanRepository(_app_config.database_url)

JOB_KIND = "swarm"


class SwarmCreateRequest(BaseModel):
    """Launch request.

    There is deliberately **no** ``goal_text``, ``prompt`` or ``custom_goal``
    field. A swarm runs a preset, so a free-text objective is unrepresentable
    rather than validated: there is nothing to sanitise and nothing to reject.
    """

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
    analysis_provider: str | None = None
    analysis_model: str | None = None
    analysis_api_key: str | None = None
    endpoint_profile: str | None = "auto"
    goal_id: str
    agents: int | None = None
    max_concurrent: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    formats: list[str] = Field(default_factory=lambda: ["json", "html", "sarif", "pdf"])
    config_path: str | None = None


def _build_config(body: SwarmCreateRequest) -> AppConfig:
    cfg = load_config(
        Path(body.config_path)
        if body.config_path
        else _config_path
        if _config_path.exists()
        else None
    )
    target_type = body.target_type.lower()
    if target_type == "endpoint":
        cfg = merge_cli_target(cfg, url=body.url)
    elif target_type == "provider":
        cfg = merge_cli_target(cfg, provider=body.provider, model=body.model)
    elif target_type == "local":
        cfg = merge_cli_target(cfg, model=body.model)
    elif target_type == "agent":
        cfg = merge_cli_target(cfg, agent=body.agent, agent_config=body.agent_config)
    elif target_type == "mcp":
        cfg = merge_cli_target(cfg, mcp=body.mcp)
    elif target_type == "rag":
        cfg = merge_cli_target(cfg, rag=body.rag, embedder=body.embedder)
    else:
        raise HTTPException(400, f"unsupported target_type: {body.target_type}")

    cfg = apply_analysis_options(
        cfg,
        analysis_provider=body.analysis_provider,
        analysis_model=body.analysis_model,
        analysis_api_key=body.analysis_api_key,
        auth_token=body.auth_token,
    )
    cfg = apply_endpoint_options(cfg, endpoint_profile=body.endpoint_profile)
    validate_target(cfg)
    return cfg


def _enforce_swarm_limits(config: AppConfig) -> None:
    """Daily and concurrent caps, reported the way the web-scan route does."""
    if not config.swarm.enabled:
        raise HTTPException(503, "Swarm is disabled (swarm.enabled=false).")

    active = job_registry.count_active(kind=JOB_KIND)
    if active >= config.swarm.max_concurrent_swarms:
        raise HTTPException(
            429,
            f"A swarm is already running "
            f"(swarm.max_concurrent_swarms={config.swarm.max_concurrent_swarms}). "
            "Cancel it or wait for it to finish.",
        )

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    today = _repo.count_scans_since(since, scan_kind="swarm")
    if today >= config.swarm.max_swarms_per_day:
        raise HTTPException(
            429,
            f"Daily swarm limit reached ({config.swarm.max_swarms_per_day} per 24h). "
            "Raise swarm.max_swarms_per_day to allow more.",
        )


# Literal paths before /{scan_id} so they are not captured by it.
@router.get("/goals")
async def list_goals() -> list[dict]:
    """The preset catalog the launch UI renders as cards."""
    config = _app_config
    return [
        {
            "id": goal.id,
            "name": goal.name,
            "description": goal.description,
            "owasp": goal.owasp,
            "suggested_agents": config.swarm.default_agents,
            "max_agents": config.swarm.max_agents,
        }
        for goal in list_swarm_goals()
    ]


@router.post("")
async def create_swarm(body: SwarmCreateRequest) -> dict:
    _repo.ensure_schema()

    if get_swarm_goal(body.goal_id) is None:
        raise HTTPException(
            400,
            f"Unknown goal '{body.goal_id}'. "
            f"Valid goals: {', '.join(list_swarm_goal_ids())}",
        )

    try:
        cfg = _build_config(body)
        cfg, agents, max_concurrent = apply_swarm_options(
            cfg,
            agents=body.agents,
            max_concurrent=body.max_concurrent,
            max_tokens=body.max_tokens,
            max_cost_usd=body.max_cost_usd,
        )
        ensure_analysis_ready(cfg)
        from agentarmor.detection.agentic.preflight import validate_analysis_key

        await validate_analysis_key(cfg)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    _enforce_swarm_limits(cfg)

    scan = build_swarm_scan(
        cfg, goal_id=body.goal_id, agents=agents, max_concurrent=max_concurrent
    )
    _repo.save_scan(scan)

    job_registry.launch(
        scan.id,
        kind=JOB_KIND,
        coro=_run_swarm_background(
            cfg,
            scan.id,
            goal_id=body.goal_id,
            agents=agents,
            max_concurrent=max_concurrent,
            formats=body.formats,
        ),
    )

    return {
        "scan_id": scan.id,
        "status": "started",
        "scan_kind": "swarm",
        "goal_id": body.goal_id,
        # Echo the effective values: a request for 500 agents is answered with
        # what will actually run rather than silently doing something else.
        "agents_requested": body.agents if body.agents is not None else agents,
        "agents": agents,
        "max_concurrent": max_concurrent,
    }


async def _run_swarm_background(
    cfg: AppConfig,
    scan_id: str,
    *,
    goal_id: str,
    agents: int,
    max_concurrent: int,
    formats: list[str],
) -> None:
    """Deep-copy the config so a later request cannot mutate a running swarm's."""
    await execute_swarm(
        cfg.model_copy(deep=True),
        goal_id=goal_id,
        agents=agents,
        max_concurrent=max_concurrent,
        scan_id=scan_id,
        formats=formats,
    )


@router.get("/{scan_id}")
async def get_swarm(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "swarm not found")
    metadata = scan.metadata or {}
    if metadata.get("scan_kind") != "swarm":
        raise HTTPException(404, "not a swarm scan")
    data = scan.model_dump(mode="json")
    data["running"] = job_registry.is_running(scan_id)
    return data


@router.post("/{scan_id}/cancel")
async def cancel_swarm(scan_id: str) -> dict:
    scan = _repo.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "swarm not found")
    cancelled = job_registry.cancel(scan_id)
    if not cancelled:
        return {"scan_id": scan_id, "cancelled": False, "status": scan.status.value}
    return {"scan_id": scan_id, "cancelled": True, "status": "cancelling"}
