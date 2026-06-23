"""High-level web scan execution service."""

from __future__ import annotations

from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Scan
from agentarmor.db.session import ScanRepository
from agentarmor.reporting import write_reports
from agentarmor.webscan.orchestrator import WebScanOrchestrator


async def execute_web_scan(
    config: AppConfig,
    scan: Scan,
    *,
    formats: list[str] | None = None,
    output_dir: Path | None = None,
) -> tuple[Scan, list[Path]]:
    repo = ScanRepository(config.database_url)
    repo.ensure_schema()
    runner = WebScanOrchestrator(config, repo)
    completed = await runner.run(scan)
    findings = repo.list_findings(scan_id=completed.id)
    paths = write_reports(config, completed, findings, output_dir, formats)
    completed.metadata["reports"] = [str(p) for p in paths]
    repo.save_scan(completed)
    return completed, paths
