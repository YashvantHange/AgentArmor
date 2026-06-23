"""Tool detector unit tests."""

from agentarmor.webscan.discovery.tool_detector import detect_tools_from_network, has_external_actions
from agentarmor.webscan.models import ToolHint


def test_network_tool_hints():
    log = [{"url": "https://example.com/api/tools/list", "method": "POST"}]
    hints = detect_tools_from_network(log)
    assert len(hints) >= 1


def test_external_actions():
    assert has_external_actions([ToolHint(name="send email")])
    assert not has_external_actions([ToolHint(name="help center")])
