"""Endpoint engine adapter."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResult
from agentarmor.engines.endpoint.client import EndpointClient


async def send_probe(
    config: AppConfig,
    probe_id: str,
    probe_name: str,
    owasp: list[str],
    request: ProbeRequest,
) -> ProbeResult:
    client = EndpointClient(config.engine_endpoint)
    return await client.chat_completion(config, probe_id, probe_name, owasp, request)
