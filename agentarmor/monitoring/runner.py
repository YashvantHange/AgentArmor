"""Execute scheduled rescans."""

from __future__ import annotations

from agentarmor.core.config import AppConfig, load_config
from agentarmor.core.config import merge_cli_target
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.monitoring.models import MonitorRunResult


async def run_scheduled_scan(
    schedule_id: str,
    *,
    repo: MonitorRepository,
    config: AppConfig | None = None,
) -> MonitorRunResult:
    from agentarmor.services.scan_service import execute_scan

    schedule = repo.get_schedule(schedule_id)
    if not schedule:
        raise ValueError(f"schedule not found: {schedule_id}")

    cfg = config or load_config(None)
    tc = schedule.target_config
    cfg = merge_cli_target(
        cfg,
        url=tc.get("url"),
        provider=tc.get("provider"),
        model=tc.get("model"),
        agent=tc.get("agent"),
        mcp=tc.get("mcp"),
        rag=tc.get("rag"),
    )

    previous_count = schedule.last_finding_count
    completed, _paths = await execute_scan(cfg, formats=["json"])
    new_count = completed.finding_count
    regressed = new_count > previous_count
    drift = regressed or (previous_count > 0 and new_count > previous_count * 1.2)

    repo.update_after_run(
        schedule_id,
        scan_id=completed.id,
        finding_count=new_count,
        drift_detected=drift,
    )

    return MonitorRunResult(
        schedule_id=schedule_id,
        scan_id=completed.id,
        finding_count=new_count,
        new_findings=max(0, new_count - previous_count),
        regressed=regressed,
    )
