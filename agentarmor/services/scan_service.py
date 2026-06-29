"""High-level scan execution service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Scan, ScanStatus
from agentarmor.db.session import ScanRepository
from agentarmor.orchestrator.runner import ScanRunner
from agentarmor.reporting import write_reports
from agentarmor.services.plan_service import enforce_plan_budget, preview_scan_plan

_log = logging.getLogger(__name__)


async def _mark_scan_failed(repo: ScanRepository, scan: Scan, error: str) -> Scan:
    failed = repo.get_scan(scan.id) or scan
    failed.status = ScanStatus.FAILED
    failed.metadata["error"] = error
    failed.completed_at = datetime.now(timezone.utc)
    repo.save_scan(failed)
    await event_bus.publish_simple(
        failed.id,
        "scan.completed",
        {"status": "failed", "error": error},
    )
    return failed


async def execute_scan(
    config: AppConfig,
    scan_id: str | None = None,
    output_dir: Path | None = None,
    formats: list[str] | None = None,
    output_file: Path | None = None,
) -> tuple[Scan, list[Path]]:
    repo = ScanRepository(config.database_url)
    repo.ensure_schema()

    if config.features.planner_v2:
        preview = await preview_scan_plan(config)
        enforce_plan_budget(config, preview)

    scan = Scan(target=config.target)
    if scan_id:
        existing = repo.get_scan(scan_id)
        if existing:
            scan = existing
        else:
            scan.id = scan_id
    runner = ScanRunner(config, repo)
    try:
        completed = await runner.run(scan)
    except Exception as exc:
        _log.exception("Scan %s execution failed", scan.id)
        await _mark_scan_failed(repo, scan, str(exc))
        raise

    try:
        findings = repo.list_findings(scan_id=completed.id)
        paths = write_reports(config, completed, findings, output_dir, formats, output_file)
        completed.metadata["reports"] = [str(p) for p in paths]
        repo.save_scan(completed)
        return completed, paths
    except Exception as exc:
        _log.exception("Scan %s report generation failed", scan.id)
        await _mark_scan_failed(repo, completed, str(exc))
        raise
