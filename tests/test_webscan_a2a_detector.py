"""A2A agent card detection tests."""

import pytest

pytest.importorskip("playwright")

from agentarmor.webscan.discovery.a2a_detector import detect_a2a


class _FakePage:
    async def content(self) -> str:
        return "<html></html>"

    async def evaluate(self, script: str, paths=None) -> list:
        return []


@pytest.mark.asyncio
async def test_agent_card_network():
    log = [{"url": "https://example.com/api/agents/list", "method": "GET"}]
    result = await detect_a2a(_FakePage(), log, "https://example.com")
    assert result.a2a_enabled
    assert result.confidence >= 0.5
