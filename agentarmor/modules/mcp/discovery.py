"""MCP tool discovery."""

from __future__ import annotations

from typing import Any

from agentarmor.modules.mcp.client import McpClient


async def discover_tools(client: McpClient, *, include_hidden: bool = False) -> list[dict[str, Any]]:
    method = "tools/list_all" if include_hidden else "tools/list"
    result = await client.request(method)
    return result.get("tools", [])


async def discover_hidden_tools(client: McpClient) -> list[dict[str, Any]]:
    public = await discover_tools(client, include_hidden=False)
    all_tools = await discover_tools(client, include_hidden=True)
    public_names = {t["name"] for t in public}
    return [t for t in all_tools if t["name"] not in public_names]
