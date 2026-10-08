"""Registry of running background jobs, so they can be counted and cancelled.

Scans launch through Starlette ``BackgroundTasks``, which runs a coroutine after
the response is sent and keeps no handle on it. That is fine for a twelve-round
red-team scan: it terminates on its own and nobody needs to stop it. It is the
wrong shape for a swarm, which can be a hundred members wide against a live
target - without a handle such a run cannot be cancelled, cannot be counted
against a concurrency limit, and cannot be drained at shutdown.

Modelled on ``MonitoringScheduler``, the one place in the codebase that already
holds an ``asyncio.Task`` and cancels it.

Deliberately in-memory. Job liveness is a property of this process, and a database
row saying "running" is stale the moment the process dies - which is exactly when
an accurate answer matters most.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


@dataclass
class Job:
    job_id: str
    kind: str
    task: asyncio.Task
    started_at: datetime


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def launch(self, job_id: str, *, kind: str, coro: Awaitable[None]) -> Job:
        """Start a coroutine as a tracked task."""
        existing = self._jobs.get(job_id)
        if existing is not None and not existing.task.done():
            return existing

        task = asyncio.ensure_future(coro)
        job = Job(
            job_id=job_id,
            kind=kind,
            task=task,
            started_at=datetime.now(timezone.utc),
        )
        self._jobs[job_id] = job

        def _done(finished: asyncio.Task) -> None:
            self._jobs.pop(job_id, None)
            if finished.cancelled():
                return
            error = finished.exception()
            if error is not None:
                # Without this the exception is swallowed until interpreter exit.
                _log.error("Job %s (%s) failed: %s", job_id, kind, error)

        task.add_done_callback(_done)
        return job

    def cancel(self, job_id: str) -> bool:
        """Request cancellation. True when a live job was asked to stop."""
        job = self._jobs.get(job_id)
        if job is None or job.task.done():
            return False
        job.task.cancel()
        return True

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def is_running(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        return job is not None and not job.task.done()

    def count_active(self, *, kind: str | None = None) -> int:
        return sum(
            1
            for job in self._jobs.values()
            if not job.task.done() and (kind is None or job.kind == kind)
        )

    def active_ids(self, *, kind: str | None = None) -> list[str]:
        return [
            job.job_id
            for job in self._jobs.values()
            if not job.task.done() and (kind is None or job.kind == kind)
        ]

    async def drain(self, *, timeout: float = 10.0) -> None:
        """Cancel every live job and wait briefly. For application shutdown."""
        jobs = [job for job in self._jobs.values() if not job.task.done()]
        for job in jobs:
            job.task.cancel()
        if not jobs:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*[job.task for job in jobs], return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            _log.warning("Timed out draining %d job(s)", len(jobs))
        self._jobs.clear()


job_registry = JobRegistry()
