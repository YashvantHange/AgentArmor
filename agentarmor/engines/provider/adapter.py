"""Provider engine adapter — LiteLLM-backed probe execution."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.engines.provider.litellm_client import SUPPORTED_PROVIDERS, completion


async def send_probe(
    config: AppConfig,
    probe_id: str,
    probe_name: str,
    owasp: list[str],
    request: ProbeRequest,
) -> ProbeResult:
    provider = config.target.provider
    if not provider:
        raise ValueError("Target provider is required. Use --provider or set [target].provider.")

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    try:
        content, raw, latency_ms = await completion(
            provider,
            request.messages,
            model=request.model or config.target.model,
            temperature=request.temperature,
        )
        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            owasp=owasp,
            request=request,
            response=ProbeResponse(content=content, raw=raw, status_code=200),
            latency_ms=latency_ms,
            metadata={"provider": provider, "model": raw.get("model", request.model)},
        )
    except Exception as exc:
        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            owasp=owasp,
            request=request,
            response=ProbeResponse(content="", raw={}, status_code=0),
            latency_ms=0.0,
            error=str(exc),
            metadata={"provider": provider},
        )
