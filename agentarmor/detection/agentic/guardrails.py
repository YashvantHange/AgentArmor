"""Guardrails for agentic enrichment — evidence and schema validation."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

_T = TypeVar("_T", bound=BaseModel)

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]+", re.I),
]


def redact_secrets(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def truncate(text: str, limit: int = 2000) -> str:
    text = redact_secrets(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def parse_json_model(raw: str, model: type[_T]) -> _T | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        return model.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None


def evidence_in_response(quotes: list[str], response_excerpt: str) -> list[str]:
    if not response_excerpt:
        return quotes[:3]
    valid: list[str] = []
    lower_resp = response_excerpt.lower()
    for q in quotes:
        q = q.strip()
        if not q:
            continue
        if q.lower() in lower_resp or any(
            part.lower() in lower_resp for part in q.split() if len(part) > 4
        ):
            valid.append(q)
    return valid[:5]


def validate_agentic_output(
    payload: dict[str, Any],
    *,
    response_excerpt: str,
    allowed_owasp: list[str],
) -> bool:
    analyst = payload.get("analyst") or {}
    quotes = analyst.get("evidence_quotes") if isinstance(analyst, dict) else []
    if quotes and response_excerpt:
        if not evidence_in_response(list(quotes), response_excerpt):
            return False
    owasp = payload.get("owasp") or {}
    if isinstance(owasp, dict):
        ids = owasp.get("owasp_ids") or []
        for oid in ids:
            if oid not in allowed_owasp and oid not in {
                "LLM01", "LLM02", "LLM04", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09",
            }:
                continue
    return True
