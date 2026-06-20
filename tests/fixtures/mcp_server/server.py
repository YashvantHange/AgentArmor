"""MCP tool definitions and handlers for test fixture."""

from __future__ import annotations

import json
from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List directory contents",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

# Hidden from normal listing — discoverable via enumeration probe
HIDDEN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "dump_secrets",
        "description": "Dump environment secrets",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

SECRETS = {
    "api_key": "sk-test-SECRET123",
    "db_password": "postgres://admin:SUPERSECRET@localhost",
}


def handle_request(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    params = params or {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/list_all":
        return {"tools": TOOLS + HIDDEN_TOOLS}
    if method == "tools/call":
        return _call_tool(params.get("name", ""), params.get("arguments") or {})
    return {"error": f"Unknown method: {method}"}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "read_file":
        path = arguments.get("path", "")
        if ".." in path or path.startswith("/etc"):
            return {
                "content": [{"type": "text", "text": f"root:x:0:0:root:/root:/bin/bash\n{SECRETS}"}],
                "isError": False,
            }
        return {"content": [{"type": "text", "text": f"contents of {path}"}]}
    if name == "write_file":
        return {"content": [{"type": "text", "text": "written"}]}
    if name == "list_directory":
        return {"content": [{"type": "text", "text": "file1.txt\nfile2.txt\n.secrets"}]}
    if name == "dump_secrets":
        return {
            "content": [{"type": "text", "text": json.dumps(SECRETS)}],
            "isError": False,
        }
    return {"content": [{"type": "text", "text": f"unknown tool {name}"}], "isError": True}


def run_stdio() -> None:
    """JSON-RPC loop on stdin/stdout (MCP-style)."""
    import sys

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params")
        result = handle_request(method, params)
        resp: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "result": result}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
