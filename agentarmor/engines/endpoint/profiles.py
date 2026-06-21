"""Endpoint request/response profiles for universal chat API scanning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agentarmor.core.config import AppConfig, EndpointEngineConfig
from agentarmor.core.models import ProbeRequest


@dataclass(frozen=True)
class EndpointProfile:
    id: str
    description: str
    build_payload: str  # marker for builder dispatch


def looks_like_page_url(url: str) -> bool:
    lowered = url.lower().split("?")[0]
    return lowered.endswith(".html") or "/lab-themes/" in lowered or "/index.html" in lowered


def extract_response_text(data: dict[str, Any], path: str | None) -> str:
    if path:
        return str(_get_path(data, path) or "")
    # OpenAI default
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        if message.get("content"):
            return str(message["content"])
    for key in ("response", "reply", "answer", "output", "text", "content", "message"):
        if key in data and isinstance(data[key], str):
            return data[key]
    if "data" in data and isinstance(data["data"], dict):
        for key in ("response", "reply", "answer", "output", "text", "content"):
            if key in data["data"]:
                return str(data["data"][key])
    return data.get("content", "") or ""


def _get_path(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def build_payload(
    app_config: AppConfig,
    request: ProbeRequest,
    *,
    profile_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (json body, resolved profile id)."""
    ep = app_config.engine_endpoint
    pid = profile_id or ep.detected_profile or ep.profile
    model = request.model or app_config.target.model or "gpt-3.5-turbo"
    prompt = _last_user_message(request)

    if pid == "custom" and ep.request_template:
        body = _from_template(ep.request_template, prompt=prompt, model=model, messages=request.messages)
        body.update(ep.extra_body or {})
        return body, "custom"

    if pid in ("openai", "openai_compat", "auto"):
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
        }
        if pid == "openai_compat":
            payload["stream"] = False
        payload.update(ep.extra_body or {})
        return payload, pid if pid != "auto" else "openai"

    # Named alternates used by auto-detect
    builders = _alternate_builders(model, prompt, request.messages)
    if pid in builders:
        body = dict(builders[pid])
        body.update(ep.extra_body or {})
        return body, pid

    payload = {
        "model": model,
        "messages": request.messages,
        "temperature": request.temperature,
    }
    payload.update(ep.extra_body or {})
    return payload, "openai"


def response_path_for_profile(profile_id: str, ep: EndpointEngineConfig) -> str | None:
    if ep.response_path:
        return ep.response_path
    return _PROFILE_RESPONSE_PATHS.get(profile_id)


def parse_http_body(
    *,
    status_code: int,
    content_type: str,
    raw_text: str,
    data: dict[str, Any],
    response_path: str | None,
) -> tuple[str, str | None]:
    """Return (content, error_message). error_message set on connectivity issues."""
    if status_code >= 400:
        return "", f"HTTP {status_code}: {raw_text[:200]}"
    if "text/html" in content_type.lower() or _looks_like_html(raw_text):
        return "", (
            "Received HTML instead of API JSON — use the chat API endpoint "
            "(DevTools → Network → copy POST URL), not the browser page URL."
        )
    if not data and raw_text and not raw_text.strip().startswith("{"):
        if _looks_like_html(raw_text):
            return "", "Response appears to be HTML, not a chat API."
        return raw_text[:8000], None
    content = extract_response_text(data, response_path)
    if not content.strip() and data:
        content = json.dumps(data)[:8000]
    return content, None


def _looks_like_html(text: str) -> bool:
    t = text.lstrip()[:500].lower()
    return t.startswith("<!doctype") or t.startswith("<html") or "<body" in t


def _last_user_message(request: ProbeRequest) -> str:
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return request.messages[-1]["content"] if request.messages else ""


def _from_template(
    template: str,
    *,
    prompt: str,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    rendered = (
        template.replace("{prompt}", json.dumps(prompt)[1:-1])
        .replace("{model}", model)
        .replace("{messages}", json.dumps(messages))
    )
    return json.loads(rendered)


def _alternate_builders(
    model: str, prompt: str, messages: list[dict[str, str]]
) -> dict[str, dict[str, Any]]:
    return {
        "message_reply": {"message": prompt, "model": model},
        "prompt_output": {"prompt": prompt, "model": model},
        "input_result": {"input": prompt, "model": model},
        "query_response": {"query": prompt, "model": model},
        "chat_messages": {"messages": messages, "model": model},
    }


_PROFILE_RESPONSE_PATHS: dict[str, str | None] = {
    "openai": None,
    "openai_compat": None,
    "message_reply": "response",
    "prompt_output": "output",
    "input_result": "result",
    "query_response": "response",
    "chat_messages": None,
    "custom": None,
}

# Order for auto-detection (profile_id, response_path override)
AUTO_PROBE_CANDIDATES: list[tuple[str, str | None]] = [
    ("openai", None),
    ("message_reply", "response"),
    ("message_reply", "reply"),
    ("prompt_output", "output"),
    ("prompt_output", "text"),
    ("input_result", "result"),
    ("query_response", "response"),
    ("chat_messages", None),
]
