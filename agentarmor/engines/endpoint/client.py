"""OpenAI-compatible HTTP client for endpoint scanning."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from agentarmor.core.config import AppConfig, EndpointEngineConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult


class RateLimiter:
    def __init__(self, rps: float) -> None:
        self._interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class EndpointClient:
    def __init__(self, config: EndpointEngineConfig) -> None:
        self._config = config
        self._limiter = RateLimiter(config.rate_limit_rps)

    async def chat_completion(
        self,
        app_config: AppConfig,
        probe_id: str,
        probe_name: str,
        owasp: list[str],
        request: ProbeRequest,
    ) -> ProbeResult:
        url = app_config.target.url
        if not url:
            raise ValueError("Target URL is required for endpoint scans")

        await self._limiter.acquire()
        payload = {
            "model": request.model or app_config.target.model or "gpt-3.5-turbo",
            "messages": request.messages,
            "temperature": request.temperature,
        }
        headers = {"Content-Type": "application/json", **app_config.target.headers}

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_s) as client:
                response = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000
                data: dict[str, Any] = {}
                content = ""
                if response.headers.get("content-type", "").startswith("application/json"):
                    data = response.json()
                    content = _extract_openai_content(data)
                else:
                    content = response.text
                return ProbeResult(
                    probe_id=probe_id,
                    probe_name=probe_name,
                    owasp=owasp,
                    request=request,
                    response=ProbeResponse(
                        content=content,
                        raw=data or {"text": content},
                        status_code=response.status_code,
                    ),
                    latency_ms=latency_ms,
                    metadata={"url": url},
                )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ProbeResult(
                probe_id=probe_id,
                probe_name=probe_name,
                owasp=owasp,
                request=request,
                response=ProbeResponse(content="", raw={}, status_code=0),
                latency_ms=latency_ms,
                error=str(exc),
            )


def _extract_openai_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return data.get("content", "") or str(data)
    message = choices[0].get("message") or {}
    return message.get("content", "") or ""
