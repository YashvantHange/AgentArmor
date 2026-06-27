"""Gandalf-like challenge page — discovery and probe execution."""

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from agentarmor.webscan.discovery.engine import discover_widget
from agentarmor.webscan.probes.executor import execute_probe
from agentarmor.webscan.probes.catalog import BASE_WEB_PROBES

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "webscan"


@pytest.mark.asyncio
async def test_gandalf_like_discovery():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "gandalf_like.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        result = await discover_widget(page, html)
        await browser.close()

    assert result.widget is not None
    assert result.widget.confidence >= 0.2
    assert "gandalf" in result.widget.input_selector.lower() or result.widget.tag_name == "textarea"


@pytest.mark.asyncio
async def test_gandalf_like_probe_execution():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "gandalf_like.html").resolve().as_uri()
    probe = BASE_WEB_PROBES[0]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        result = await discover_widget(page, html)
        assert result.widget is not None
        stable = await execute_probe(
            page,
            result.widget,
            probe,
            stable_ms=200,
            max_wait_ms=5000,
        )
        await browser.close()

    assert stable.text
    assert "password" in stable.text.lower() or "cannot" in stable.text.lower()
