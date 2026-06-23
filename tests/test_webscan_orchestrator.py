"""Orchestrator unit tests with mocked browser."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ScanStatus
from agentarmor.webscan.models import DiscoveryResult, StableResponse, WidgetCandidate
from agentarmor.webscan.orchestrator import WebScanOrchestrator, build_web_scan


@pytest.mark.asyncio
async def test_run_fails_on_no_widget():
    cfg = AppConfig()
    repo = MagicMock()
    repo.save_scan = MagicMock()
    scan = build_web_scan("https://allowed.com/page")
    orchestrator = WebScanOrchestrator(cfg, repo)

    mock_widget = DiscoveryResult(page_url="https://allowed.com/page", widget=None, error="no widget")
    mock_page = AsyncMock()

    class FakeCM:
        async def __aenter__(self):
            ctx = AsyncMock()
            ctx.new_page = AsyncMock(return_value=mock_page)
            return ctx

        async def __aexit__(self, *args):
            return None

    orchestrator._pool.context = MagicMock(return_value=FakeCM())
    orchestrator._pool.close = AsyncMock()

    with patch("agentarmor.webscan.orchestrator.BrowserSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value = mock_session
        mock_session.network_log = []

        with patch("agentarmor.webscan.orchestrator.discover_full", AsyncMock(return_value=mock_widget)):
            with patch("agentarmor.webscan.orchestrator.event_bus.publish_simple", AsyncMock()):
                result = await orchestrator.run(scan)

    assert result.status == ScanStatus.FAILED
    err = result.metadata.get("error") or ""
    assert "widget" in err.lower()


def test_build_web_scan_metadata():
    scan = build_web_scan("https://example.com", owasp_filters=["LLM01"])
    assert scan.metadata["scan_kind"] == "web"
    assert scan.metadata["page_url"] == "https://example.com"
    assert scan.metadata["owasp_filters"] == ["LLM01"]
