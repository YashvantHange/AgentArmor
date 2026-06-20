"""MCP client — stdio and HTTP transports."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx


class McpClient:
    def __init__(
        self,
        target: str,
        *,
        transport: str = "stdio",
        timeout_s: float = 30.0,
    ) -> None:
        self._target = target
        if target.startswith("http://") or target.startswith("https://"):
            self._transport = "http"
        else:
            self._transport = transport
        self._timeout = timeout_s
        self._request_id = 0
        self._process: asyncio.subprocess.Process | None = None

    async def __aenter__(self) -> McpClient:
        if self._transport == "stdio":
            script = self._resolve_stdio_script()
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()

    def _resolve_stdio_script(self) -> Path:
        path = Path(self._target)
        if path.is_file():
            return path
        # Built-in fixture
        return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mcp_server" / "server.py"

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        if self._transport == "http":
            url = self._target.rstrip("/") + "/mcp"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        else:
            data = await self._stdio_request(payload)
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result", data)

    async def _stdio_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("stdio MCP process not started")
        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()
        raw = await asyncio.wait_for(self._process.stdout.readline(), timeout=self._timeout)
        return json.loads(raw.decode())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self.request("tools/call", {"name": name, "arguments": arguments})
