"""Anonymize sensitive content in research exports."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_API_KEY = re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]+)\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def anonymize_text(text: str) -> str:
    if not text:
        return text
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _API_KEY.sub("[REDACTED_SECRET]", text)
    text = _IPV4.sub("[REDACTED_IP]", text)
    return text
