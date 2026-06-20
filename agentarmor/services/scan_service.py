"""High-level scan execution service."""

from __future__ import annotations

from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Scan
from agentarmor.db.session import ScanRepository
from agentarmor.orchestrator.runner import ScanRunner
from agentarmor.reporting import write_reports


async def execute_scan(
    config: AppConfig,
    scan_id: str | None = None,
    output_dir: Path | None = None,
    formats: list[str] | None = None,
    output_file: Path | None = None,
) -> tuple[Scan, list[Path]]:
    repo = ScanRepository(config.database_url)
    repo.ensure_schema()

    scan = Scan(target=config.target)
    if scan_id:
        scan.id = scan_id
    runner = ScanRunner(config, repo)
    completed = await runner.run(scan)
    findings = repo.list_findings(scan_id=completed.id)
    paths = write_reports(config, completed, findings, output_dir, formats, output_file)
    completed.metadata["reports"] = [str(p) for p in paths]
    repo.save_scan(completed)
    return completed, paths
