"""High-level swarm execution service.

The single seam the API and the CLI both call, exactly as both call
``execute_scan``. The difference between the two callers is only who owns the id
and the event loop: the API pre-creates the scan row and passes ``scan_id``, while
the CLI lets this function mint one and runs it under ``asyncio.run``.

Reuses ``_mark_scan_failed`` and ``_annotate_analysis_health`` from the scan
service rather than reimplementing them - the failure marker already publishes the
terminal ``scan.completed`` event that stops the SSE stream.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Scan, ScanStatus
from agentarmor.db.session import ScanRepository
from agentarmor.reporting import write_reports
from agentarmor.services.scan_service import _annotate_analysis_health, _mark_scan_failed
from agentarmor.swarm.coordinator import SwarmCoordinator
from agentarmor.swarm.goals import get_swarm_goal, list_swarm_goal_ids

_log = logging.getLogger(__name__)


def build_swarm_scan(
    config: AppConfig,
    *,
    goal_id: str,
    agents: int,
    max_concurrent: int,
) -> Scan:
    """Create the scan row for a swarm run.

    ``scan_kind`` marks it as a swarm the same way web scans mark themselves, which
    is what lets the existing findings, events and report endpoints serve it
    without a schema change.
    """
    scan = Scan(target=config.target)
    scan.metadata.update(
        {
            "scan_kind": "swarm",
            "scan_mode": "swarm",
            "goal_id": goal_id,
            "agent_count": agents,
            "max_concurrent": max_concurrent,
        }
    )
    return scan


async def _mark_swarm_cancelled(repo: ScanRepository, scan: Scan) -> Scan:
    """Record a cancellation, keeping whatever the run already produced.

    The coordinator has already written the partial trace and blackboard, so this
    only needs to settle the row and close the event stream.
    """
    stored = repo.get_scan(scan.id)
    already_settled = stored is not None and stored.status == ScanStatus.CANCELLED
    cancelled = stored or scan
    cancelled.status = ScanStatus.CANCELLED
    if not cancelled.completed_at:
        cancelled.completed_at = datetime.now(timezone.utc)
    repo.save_scan(cancelled)
    if not already_settled:
        # Only when the coordinator did not get far enough to emit its own
        # terminator. A second scan.completed is harmless - the SSE generator has
        # already broken on the first - but it would show up as a duplicate in any
        # consumer that logs the stream.
        await event_bus.publish_simple(
            cancelled.id,
            "scan.completed",
            {"status": "cancelled", "scan_kind": "swarm"},
        )
    return cancelled


async def execute_swarm(
    config: AppConfig,
    *,
    goal_id: str,
    agents: int,
    max_concurrent: int,
    scan_id: str | None = None,
    output_dir: Path | None = None,
    formats: list[str] | None = None,
    output_file: Path | None = None,
) -> tuple[Scan, list[Path]]:
    repo = ScanRepository(config.database_url)
    repo.ensure_schema()

    if get_swarm_goal(goal_id) is None:
        raise ValueError(
            f"Unknown swarm goal '{goal_id}'. "
            f"Choose one of: {', '.join(list_swarm_goal_ids())}"
        )

    scan = build_swarm_scan(
        config, goal_id=goal_id, agents=agents, max_concurrent=max_concurrent
    )
    if scan_id:
        existing = repo.get_scan(scan_id)
        if existing:
            existing.metadata.update(scan.metadata)
            scan = existing
        else:
            scan.id = scan_id

    try:
        completed = await SwarmCoordinator(config, repo).run(scan)
    except asyncio.CancelledError:
        await _mark_swarm_cancelled(repo, scan)
        raise
    except Exception as exc:
        _log.exception("Swarm %s execution failed", scan.id)
        await _mark_scan_failed(repo, scan, str(exc))
        raise

    try:
        findings = repo.list_findings(scan_id=completed.id)
        _annotate_analysis_health(config, completed, findings)
        paths = write_reports(config, completed, findings, output_dir, formats, output_file)
        completed.metadata["reports"] = [str(p) for p in paths]
        repo.save_scan(completed)
        return completed, paths
    except Exception as exc:
        _log.exception("Swarm %s report generation failed", scan.id)
        await _mark_scan_failed(repo, completed, str(exc))
        raise
