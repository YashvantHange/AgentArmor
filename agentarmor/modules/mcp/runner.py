"""MCP security module runner."""

from __future__ import annotations

import time

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.modules.mcp.client import McpClient
from agentarmor.modules.mcp.probes import McpProbe, get_mcp_probes


async def run_mcp_probe(config: AppConfig, probe: McpProbe) -> ProbeResult:
    target = config.target.mcp_target
    if not target:
        raise ValueError("MCP target is required")
    transport = config.target.mcp_transport or config.module_mcp.transport
    start = time.perf_counter()
    try:
        async with McpClient(
            target, transport=transport, timeout_s=config.module_mcp.timeout_s
        ) as client:
            triggered, summary, raw = await probe.run(client, config)
        content = f"[FINDING] {summary}" if triggered else summary
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(messages=[{"role": "user", "content": probe.id}]),
            response=ProbeResponse(content=content, raw={**raw, "triggered": triggered}),
            latency_ms=latency_ms,
            metadata={"module": "mcp", "transport": transport, "triggered": triggered},
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(messages=[]),
            response=ProbeResponse(content="", raw={}),
            latency_ms=latency_ms,
            error=str(exc),
            metadata={"module": "mcp"},
        )


def list_mcp_probes() -> list[McpProbe]:
    return get_mcp_probes()
