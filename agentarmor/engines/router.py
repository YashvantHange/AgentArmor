"""Engine router — dispatches probes to endpoint, provider, or local backends."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResult, TargetType
from agentarmor.engines.endpoint.adapter import send_probe as endpoint_send_probe
from agentarmor.engines.local.adapter import send_probe as local_send_probe
from agentarmor.engines.provider.adapter import send_probe as provider_send_probe
from agentarmor.modules.router import is_module_target, validate_module_target


def validate_target(config: AppConfig) -> None:
    if is_module_target(config):
        validate_module_target(config)
        return

    target = config.target
    if target.type == TargetType.ENDPOINT:
        if not target.url:
            raise ValueError("Target URL is required. Use --url or set [target].url in config.")
    elif target.type == TargetType.PROVIDER:
        if not target.provider:
            raise ValueError(
                "Target provider is required. Use --provider or set [target].provider in config."
            )
    elif target.type == TargetType.LOCAL:
        if not target.model:
            raise ValueError(
                "Target model path is required. Use --model or set [target].model in config."
            )
    else:
        raise ValueError(f"Target type '{target.type.value}' is not supported.")


async def send_probe(
    config: AppConfig,
    probe_id: str,
    probe_name: str,
    owasp: list[str],
    request: ProbeRequest,
) -> ProbeResult:
    validate_target(config)
    target_type = config.target.type
    if target_type == TargetType.ENDPOINT:
        return await endpoint_send_probe(config, probe_id, probe_name, owasp, request)
    if target_type == TargetType.PROVIDER:
        return await provider_send_probe(config, probe_id, probe_name, owasp, request)
    if target_type == TargetType.LOCAL:
        return await local_send_probe(config, probe_id, probe_name, owasp, request)
    raise ValueError(f"No engine registered for target type '{target_type.value}'.")
