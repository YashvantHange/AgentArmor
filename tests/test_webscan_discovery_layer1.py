"""Response stability detector tests (Playwright)."""

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from agentarmor.webscan.discovery.engine import discover_widget
from agentarmor.webscan.models import WidgetCandidate
from agentarmor.webscan.probes.response_stability import wait_stable_response

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "webscan"


@pytest.mark.asyncio
async def test_streaming_fixture_stabilizes():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "streaming_chat.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        widget = WidgetCandidate(
            input_selector="#prompt",
            send_selector="#go",
            confidence=0.9,
        )
        await page.locator("#prompt").fill("hello")
        await page.locator("#go").click()
        stable = await wait_stable_response(
            page, widget, stable_ms=200, poll_ms=50, max_wait_ms=5000
        )
        await browser.close()
    assert "reveal" in stable.text.lower() or "hidden" in stable.text.lower() or "cannot" in stable.text.lower()
    assert stable.wait_ms > 0


@pytest.mark.asyncio
async def test_basic_chat_discovery():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "basic_chat.html").resolve().as_uri()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        result = await discover_widget(page, html)
        await browser.close()
    assert result.widget is not None
    assert result.widget.confidence >= 0.2
    assert "chat" in result.widget.input_selector.lower() or "textarea" in result.widget.tag_name
