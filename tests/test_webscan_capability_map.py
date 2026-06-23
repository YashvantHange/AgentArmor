"""Capability map builder tests."""

import pytest

pytest.importorskip("playwright")

from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.webscan.discovery.capability_map import build_capability_map

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "webscan"


@pytest.mark.asyncio
async def test_rag_widget_detected():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "rag_widget.html").resolve().as_uri()
    cfg = AppConfig()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        cap, profile, tools = await build_capability_map(page, [], html, None, cfg)
        await browser.close()
    assert cap.rag is True


@pytest.mark.asyncio
async def test_tool_actions_detected():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "tool_actions.html").resolve().as_uri()
    cfg = AppConfig()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        cap, profile, tools = await build_capability_map(page, [], html, None, cfg)
        await browser.close()
    assert len(cap.tools) >= 2
    assert profile.tool_count >= 2


@pytest.mark.asyncio
async def test_memory_detected():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "memory_chat.html").resolve().as_uri()
    cfg = AppConfig()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        cap, _, _ = await build_capability_map(page, [], html, None, cfg)
        await browser.close()
    assert cap.memory is True


@pytest.mark.asyncio
async def test_mcp_markers_detected():
    from playwright.async_api import async_playwright

    html = (FIXTURES / "mcp_jsonrpc.html").resolve().as_uri()
    cfg = AppConfig()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(html)
        cap, _, _ = await build_capability_map(page, [], html, None, cfg)
        await browser.close()
    assert cap.mcp is True
