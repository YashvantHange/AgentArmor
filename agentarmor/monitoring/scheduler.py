"""Background scheduler for continuous monitoring."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from agentarmor.core.config import AppConfig
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.monitoring.runner import run_scheduled_scan

logger = logging.getLogger(__name__)

_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


class MonitoringScheduler:
    def __init__(self, repo: MonitorRepository, config: AppConfig) -> None:
        self._repo = repo
        self._config = config
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as exc:
                logger.warning("monitoring tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        for schedule in self._repo.list_schedules():
            if not schedule.enabled or schedule.cron == "manual":
                continue
            interval = _INTERVALS.get(schedule.cron)
            if not interval:
                continue
            last = None
            if schedule.last_run_at:
                last = datetime.fromisoformat(schedule.last_run_at.replace("Z", "+00:00"))
            if last and now - last < interval:
                continue
            await run_scheduled_scan(schedule.id, repo=self._repo, config=self._config)
