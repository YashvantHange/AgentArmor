"""Auto-detect endpoint API profile by probing the target URL."""

from __future__ import annotations

import time
from typing import Any

import httpx

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest
from agentarmor.engines.endpoint.profiles import (
    AUTO_PROBE_CANDIDATES,
    build_payload,
    extract_response_text,
    looks_like_page_url,
    parse_http_body,
)


async def autodetect_profile(app_config: AppConfig) -> dict[str, Any]:
    url = app_config.target.url or ""
    if not url:
        return {"ok": False, "error": "URL is required"}
    if looks_like_page_url(url):
        return {
            "ok": False,
            "error": (
                "This looks like a browser page URL (.html). "
                "Open DevTools → Network, send a chat message, and copy the POST API URL."
            ),
            "hint": "page_url_rejected",
        }

    ep = app_config.engine_endpoint
    if ep.profile != "auto":
        return {"ok": True, "profile": ep.profile, "auto_detected": False}

    headers = {"Content-Type": "application/json", **(app_config.target.headers or {})}
    ping = ProbeRequest(messages=[{"role": "user", "content": "ping"}], model=app_config.target.model)

    async with httpx.AsyncClient(timeout=ep.timeout_s) as client:
        for profile_id, response_path in AUTO_PROBE_CANDIDATES:
            ep.detected_profile = profile_id
            payload, _ = build_payload(app_config, ping, profile_id=profile_id)
            try:
                start = time.perf_counter()
                response = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000
                content_type = response.headers.get("content-type", "")
                raw = response.text
                data: dict[str, Any] = {}
                if "json" in content_type.lower():
                    try:
                        data = response.json()
                    except Exception:
                        data = {}
                text, err = parse_http_body(
                    status_code=response.status_code,
                    content_type=content_type,
                    raw_text=raw,
                    data=data,
                    response_path=response_path,
                )
                if err or response.status_code >= 400:
                    continue
                if text.strip():
                    app_config.engine_endpoint.detected_profile = profile_id
                    if response_path:
                        app_config.engine_endpoint.response_path = response_path
                    return {
                        "ok": True,
                        "profile": profile_id,
                        "response_path": response_path,
                        "auto_detected": True,
                        "latency_ms": round(latency_ms, 1),
                        "sample_excerpt": text[:200],
                        "status_code": response.status_code,
                    }
                # empty but valid json — still accept openai shape
                if data and profile_id == "openai":
                    app_config.engine_endpoint.detected_profile = "openai"
                    return {
                        "ok": True,
                        "profile": "openai",
                        "auto_detected": True,
                        "latency_ms": round(latency_ms, 1),
                        "sample_excerpt": extract_response_text(data, None)[:200],
                        "status_code": response.status_code,
                    }
            except Exception:
                continue

    return {
        "ok": False,
        "error": "Could not auto-detect API format. Try Advanced → custom JSON template.",
        "hint": "autodetect_failed",
    }
