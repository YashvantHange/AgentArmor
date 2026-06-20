"""OWASP LLM mapping helpers."""

from __future__ import annotations

OWASP_NAMES = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM09": "Overreliance",
}


def rule_id(owasp_id: str) -> str:
    return f"agentarmor/owasp/{owasp_id.lower()}"


def rule_name(owasp_id: str) -> str:
    return OWASP_NAMES.get(owasp_id, owasp_id)
