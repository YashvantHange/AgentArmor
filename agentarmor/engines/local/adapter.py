"""Local model engine adapter."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from agentarmor.core.config import AppConfig, LocalEngineConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.engines.local.router import LocalModelRouter


@lru_cache(maxsize=4)
def _get_router(model_path: str, backend: str, gpu_layers: int, memory_warn_gb: float) -> LocalModelRouter:
    return LocalModelRouter(
        Path(model_path),
        backend=backend,
        gpu_layers=gpu_layers,
        memory_warn_gb=memory_warn_gb,
    )


async def send_probe(
    config: AppConfig,
    probe_id: str,
    probe_name: str,
    owasp: list[str],
    request: ProbeRequest,
) -> ProbeResult:
    model = config.target.model
    if not model:
        raise ValueError("Target model path is required. Use --model or set [target].model.")

    local_cfg: LocalEngineConfig = config.engine_local
    router = _get_router(
        model,
        local_cfg.backend,
        local_cfg.gpu_layers,
        local_cfg.memory_warn_gb,
    )

    try:
        content, raw, latency_ms = await asyncio.to_thread(
            router.complete,
            request.messages,
            temperature=request.temperature,
        )
        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            owasp=owasp,
            request=request,
            response=ProbeResponse(content=content, raw=raw, status_code=200),
            latency_ms=latency_ms,
            metadata={"backend": router.backend_type.value, "model_path": model},
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
            metadata={"model_path": model},
        )
