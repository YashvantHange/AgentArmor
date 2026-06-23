"""In-process headed browser sessions for manual SSO login."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.webscan.browser.pool import BrowserPool
from agentarmor.webscan.browser.session import BrowserSession
from agentarmor.webscan.url_validator import validate_page_url


@dataclass
class _ActiveAuthSession:
    pool: BrowserPool
    context: Any
    page: Any
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AuthSessionManager:
    """Keeps headed browser contexts open until the user completes login."""

    def __init__(self) -> None:
        self._sessions: dict[str, _ActiveAuthSession] = {}
        self._lock = asyncio.Lock()

    async def prepare(self, scan_id: str, page_url: str, config: AppConfig) -> None:
        validated = validate_page_url(
            page_url,
            allowlist=config.webscan.allowlist,
            blocklist=config.webscan.blocklist,
        )
        if not validated.ok:
            raise ValueError(validated.error or "invalid URL")

        pool = BrowserPool(max_concurrent=1, headless=False)
        browser = await pool._ensure_browser()
        context = await browser.new_context(
            ignore_https_errors=False,
            java_script_enabled=True,
        )
        page = await context.new_page()
        session = BrowserSession(
            page,
            allowlist=config.webscan.allowlist,
            blocklist=config.webscan.blocklist,
        )
        await session.goto(
            validated.normalized_url,
            timeout_ms=int(config.webscan.timeout_s * 1000),
        )

        async with self._lock:
            existing = self._sessions.pop(scan_id, None)
            if existing:
                await self._close_session(existing)
            self._sessions[scan_id] = _ActiveAuthSession(pool=pool, context=context, page=page)

    async def finalize(self, scan_id: str) -> dict[str, Any]:
        async with self._lock:
            active = self._sessions.pop(scan_id, None)
        if not active:
            raise KeyError(f"no active auth session for scan {scan_id}")
        async with active.lock:
            state = await active.context.storage_state()
            await self._close_session(active)
            return state

    async def cancel(self, scan_id: str) -> None:
        async with self._lock:
            active = self._sessions.pop(scan_id, None)
        if active:
            await self._close_session(active)

    async def _close_session(self, active: _ActiveAuthSession) -> None:
        try:
            await active.context.close()
        except Exception:
            pass
        try:
            await active.pool.close()
        except Exception:
            pass


auth_session_manager = AuthSessionManager()
