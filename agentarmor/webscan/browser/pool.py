"""Playwright browser pool with concurrency limits."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


class BrowserPool:
    """Lazy Playwright pool — one browser, semaphore-limited contexts."""

    def __init__(self, max_concurrent: int = 2, headless: bool = True) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._headless = headless
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> Browser:
        if not playwright_available():
            raise RuntimeError(
                "Playwright is not installed. Run: pip install 'agentarmor[browser]' "
                "&& agentarmor browser install"
            )
        async with self._lock:
            if self._browser is not None:
                return self._browser
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            return self._browser

    @asynccontextmanager
    async def context(
        self,
        *,
        storage_state: dict | None = None,
        headless: bool | None = None,
    ) -> AsyncIterator[BrowserContext]:
        async with self._semaphore:
            use_headless = self._headless if headless is None else headless
            if use_headless != self._headless and self._browser is not None:
                await self.close()
            if use_headless != self._headless:
                self._headless = use_headless
            browser = await self._ensure_browser()
            ctx_kwargs: dict = {
                "ignore_https_errors": False,
                "java_script_enabled": True,
            }
            if storage_state:
                ctx_kwargs["storage_state"] = storage_state
            ctx = await browser.new_context(**ctx_kwargs)
            try:
                yield ctx
            finally:
                await ctx.close()

    async def close(self) -> None:
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
