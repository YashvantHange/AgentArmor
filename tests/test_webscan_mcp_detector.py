"""MCP detector unit tests."""

from agentarmor.webscan.discovery.mcp_detector import _scan_network_for_mcp


def test_jsonrpc_network():
    log = [{"url": "https://app.example.com/mcp", "method": "POST"}]
    result = _scan_network_for_mcp(log)
    assert result.mcp_enabled
    assert result.confidence >= 0.5
