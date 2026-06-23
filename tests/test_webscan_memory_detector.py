"""Memory detector unit tests."""

import pytest

pytest.importorskip("playwright")

from pathlib import Path

from agentarmor.webscan.discovery.memory_detector import detect_memory

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "webscan"


@pytest.mark.asyncio
async def test_memory_dom():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "memory_chat.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        result = await detect_memory(page, [])
        await browser.close()
    assert result.memory_enabled
    assert len(result.indicators) >= 2
