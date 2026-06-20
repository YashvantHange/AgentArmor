"""In-process event bus for scan progress (SSE)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from agentarmor.core.models import ScanEvent


class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[ScanEvent]]] = defaultdict(list)

    def subscribe(self, scan_id: str) -> asyncio.Queue[ScanEvent]:
        queue: asyncio.Queue[ScanEvent] = asyncio.Queue()
        self._queues[scan_id].append(queue)
        return queue

    def unsubscribe(self, scan_id: str, queue: asyncio.Queue[ScanEvent]) -> None:
        if scan_id in self._queues and queue in self._queues[scan_id]:
            self._queues[scan_id].remove(queue)

    async def publish(self, event: ScanEvent) -> None:
        for queue in self._queues.get(event.scan_id, []):
            await queue.put(event)

    async def publish_simple(
        self, scan_id: str, event_name: str, data: dict[str, Any] | None = None
    ) -> None:
        await self.publish(ScanEvent(event=event_name, scan_id=scan_id, data=data or {}))


event_bus = EventBus()
