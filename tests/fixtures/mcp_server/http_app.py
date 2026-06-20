"""HTTP MCP fixture for integration tests."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from tests.fixtures.mcp_server.server import handle_request

app = FastAPI()


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict | None = None


@app.post("/mcp")
def mcp_endpoint(req: JsonRpcRequest) -> dict:
    result = handle_request(req.method, req.params)
    return {"jsonrpc": "2.0", "id": req.id, "result": result}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
