"""OpenAI-compatible and custom-profile HTTP client for endpoint scanning."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from agentarmor.core.config import AppConfig, EndpointEngineConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.engines.endpoint.autodetect import autodetect_profile
from agentarmor.engines.endpoint.profiles import (
    build_payload,
    looks_like_page_url,
    parse_http_body,
    response_path_for_profile,
)


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
        self._autodetect_done = False

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

        if looks_like_page_url(url):
            return _error_probe(
                probe_id,
                probe_name,
                owasp,
                request,
                url,
                "URL appears to be a browser page (.html), not a chat API endpoint.",
            )

        if app_config.engine_endpoint.profile == "auto" and not self._autodetect_done:
            detect = await autodetect_profile(app_config)
            self._autodetect_done = True
            if not detect.get("ok"):
                return _error_probe(
                    probe_id,
                    probe_name,
                    owasp,
                    request,
                    url,
                    str(detect.get("error", "auto-detect failed")),
                    metadata_extra={"autodetect": detect},
                )

        await self._limiter.acquire()
        ep = app_config.engine_endpoint
        profile_id = ep.detected_profile or ep.profile
        payload, resolved = build_payload(app_config, request, profile_id=profile_id)
        headers = {"Content-Type": "application/json", **(app_config.target.headers or {})}
        resp_path = response_path_for_profile(resolved, ep)

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_s) as client:
                method = (ep.http_method or "POST").upper()
                if method == "POST":
                    response = await client.post(url, json=payload, headers=headers)
                else:
                    response = await client.request(method, url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000
                content_type = response.headers.get("content-type", "")
                raw_text = response.text
                data: dict[str, Any] = {}
                if "json" in content_type.lower():
                    try:
                        data = response.json()
                    except Exception:
                        data = {}

                content, parse_error = parse_http_body(
                    status_code=response.status_code,
                    content_type=content_type,
                    raw_text=raw_text,
                    data=data,
                    response_path=resp_path,
                )
                error = parse_error
                return ProbeResult(
                    probe_id=probe_id,
                    probe_name=probe_name,
                    owasp=owasp,
                    request=request,
                    response=ProbeResponse(
                        content=content,
                        raw=data or {"text": raw_text[:2000]},
                        status_code=response.status_code,
                    ),
                    latency_ms=latency_ms,
                    error=error,
                    metadata={
                        "url": url,
                        "profile": resolved,
                        "response_path": resp_path,
                    },
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


def _error_probe(
    probe_id: str,
    probe_name: str,
    owasp: list[str],
    request: ProbeRequest,
    url: str,
    error: str,
    metadata_extra: dict[str, Any] | None = None,
) -> ProbeResult:
    meta = {"url": url, **(metadata_extra or {})}
    return ProbeResult(
        probe_id=probe_id,
        probe_name=probe_name,
        owasp=owasp,
        request=request,
        response=ProbeResponse(content="", raw={}, status_code=0),
        latency_ms=0.0,
        error=error,
        metadata=meta,
    )


def _extract_openai_content(data: dict[str, Any]) -> str:
    """Legacy helper for tests."""
    from agentarmor.engines.endpoint.profiles import extract_response_text

    return extract_response_text(data, None)
