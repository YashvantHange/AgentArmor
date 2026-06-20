"""MCP module tests."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Target, TargetType
from agentarmor.modules.mcp.probes import get_mcp_probes
from agentarmor.modules.mcp.runner import run_mcp_probe
from tests.fixtures.mcp_server.http_app import app as mcp_http_app


@pytest.fixture
def mcp_stdio_target():
    return str(Path(__file__).resolve().parent / "fixtures" / "mcp_server" / "server.py")


def test_mcp_probe_count():
    assert len(get_mcp_probes()) == 5


@pytest.mark.asyncio
async def test_mcp_stdio_scan(mcp_stdio_target):
    cfg = AppConfig(
        target=Target(type=TargetType.MCP, mcp_target=mcp_stdio_target, mcp_transport="stdio"),
    )
    probe = next(p for p in get_mcp_probes() if p.id == "mcp.tool-enumeration")
    result = await run_mcp_probe(cfg, probe)
    assert result.error is None
    assert result.metadata.get("triggered") is True


@pytest.mark.asyncio
async def test_mcp_http_scan(monkeypatch):
    transport = ASGITransport(app=mcp_http_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as http:

        async def fake_post(self, url, **kwargs):
            return await http.post(url.replace("http://testserver", ""), **kwargs)

        import httpx as httpx_module

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            post = fake_post

        monkeypatch.setattr(httpx_module, "AsyncClient", FakeAsyncClient)

        cfg = AppConfig(
            target=Target(
                type=TargetType.MCP,
                mcp_target="http://testserver",
                mcp_transport="http",
            ),
        )
        probe = next(p for p in get_mcp_probes() if p.id == "mcp.data-leakage")
        result = await run_mcp_probe(cfg, probe)
        assert result.error is None
        assert result.metadata.get("triggered") is True
