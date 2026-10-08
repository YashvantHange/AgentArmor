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
    """HTTP client for one endpoint target.

    Holds the rate limiter, the pooled ``httpx.AsyncClient`` and the cached
    auto-detect outcome, so all three are shared by every probe sent to the same
    target. See ``agentarmor.engines.endpoint.pool.get_endpoint_client``: building
    a client per probe silently disabled ``rate_limit_rps``.
    """

    def __init__(self, config: EndpointEngineConfig) -> None:
        self._config = config
        self._limiter = RateLimiter(config.rate_limit_rps)
        # The auto-detect *outcome*, not a boolean. A boolean flag would let a
        # failed detection be skipped on later probes, which then send requests
        # with an unresolved profile instead of reporting the failure.
        self._autodetect: dict[str, Any] | None = None
        self._http_client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        """Lazily create the shared client so connections are reused per target."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self._config.timeout_s)
        return self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
        self._http_client = None

    async def _resolve_profile(self, app_config: AppConfig) -> dict[str, Any]:
        """Run auto-detect once per target, then replay the result onto this config.

        ``autodetect_profile`` records the resolved profile by mutating the config
        it is handed. A pooled client is reused across scans, each of which gets
        its own deep-copied config, so a cached success has to be re-applied or
        the later scan falls back to the unresolved ``auto`` profile.
        """
        if self._autodetect is None:
            self._autodetect = await autodetect_profile(app_config)
            return self._autodetect

        detect = self._autodetect
        if detect.get("ok"):
            ep = app_config.engine_endpoint
            profile = detect.get("profile")
            if profile:
                ep.detected_profile = str(profile)
            response_path = detect.get("response_path")
            if response_path:
                ep.response_path = str(response_path)
        return detect

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

        if app_config.engine_endpoint.profile == "auto":
            detect = await self._resolve_profile(app_config)
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
            client = self._http()
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
