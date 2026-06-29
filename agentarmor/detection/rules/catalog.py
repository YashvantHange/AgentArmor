"""Unified security rule catalog — single source for L1, L2, and L4 outcome layers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

RULE_CATALOG_VERSION = "2026.06.1"

_CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yaml"


@dataclass(frozen=True)
class SecurityRule:
    name: str
    pattern: str
    category: str
    l1_weight: float = 0.0
    l2_class: str | None = None
    l2_weight: float = 0.0
    outcome_weight: float = 0.0


@lru_cache(maxsize=1)
def _load_raw_rules() -> list[SecurityRule]:
    if _CATALOG_PATH.exists():
        data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
        rules = []
        for item in data.get("rules", []):
            rules.append(
                SecurityRule(
                    name=str(item["name"]),
                    pattern=str(item["pattern"]),
                    category=str(item.get("category", "unknown")),
                    l1_weight=float(item.get("l1_weight", 0.0)),
                    l2_class=item.get("l2_class"),
                    l2_weight=float(item.get("l2_weight", 0.0)),
                    outcome_weight=float(item.get("outcome_weight", 0.0)),
                )
            )
        return rules
    return _builtin_rules()


def _builtin_rules() -> list[SecurityRule]:
    """Embedded catalog when YAML is unavailable."""
    specs = [
        ("ignore_instructions", r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions", "jailbreak", 0.85, "prompt_injection", 0.9, 0.0),
        ("disregard_prompt", r"(?i)disregard\s+(your\s+)?(system\s+)?prompt", "jailbreak", 0.85, "prompt_injection", 0.85, 0.0),
        ("developer_mode", r"(?i)you\s+are\s+now\s+(in\s+)?(developer|admin|root)\s+mode", "jailbreak", 0.80, "jailbreak", 0.85, 0.0),
        ("dan_jailbreak", r"(?i)do\s+anything\s+now|\bDAN\b", "jailbreak", 0.90, "jailbreak", 0.92, 0.0),
        ("system_prompt_leak", r"(?i)system\s*prompt\s*(is|:)", "prompt_leakage", 0.75, "data_leakage", 0.85, 0.85),
        ("my_system_prompt", r"(?i)my\s+system\s+prompt\s+is", "prompt_leakage", 0.80, "data_leakage", 0.88, 0.0),
        ("instructions_are", r"(?i)my\s+instructions\s+are", "prompt_leakage", 0.75, None, 0.0, 0.0),
        ("hidden_rules", r"(?i)hidden\s+rules?", "prompt_leakage", 0.70, "data_leakage", 0.8, 0.0),
        ("begin_system", r"(?i)BEGIN\s+SYSTEM", "system_exposure", 0.80, None, 0.0, 0.0),
        ("refusal_bypass", r"(?i)(without\s+restrictions|no\s+ethical\s+guidelines|uncensored)", "refusal_bypass", 0.65, "jailbreak", 0.85, 0.0),
        ("secret_exposure", r"(?i)here\s+is\s+(the\s+)?(secret|password|api[_\s]?key)", "prompt_leakage", 0.70, None, 0.0, 0.0),
        ("admin_discount", r"(?i)admin\s*(discount|code|coupon)", "policy_bypass", 0.85, None, 0.0, 0.9),
        ("coupon_token", r"(?i)\b[A-Z]{4,}\d{2,}OFF\b", "policy_bypass", 0.85, None, 0.0, 0.85),
        ("discount_revealed", r"(?i)discount\s*(code\s*)?(revealed|applied)", "policy_bypass", 0.0, None, 0.0, 0.85),
        ("secret_leak", r"(?i)(api[_\s-]?key|password|secret)\s*[:=]\s*\S+", "prompt_leakage", 0.0, "unsafe_output", 0.75, 0.9),
        ("privileged_pricing", r"(?i)(90|99)\s*%\s*off", "policy_bypass", 0.0, None, 0.0, 0.8),
        ("policy_disclosure", r"(?i)you\s+are\s+a\s+.+\s+assistant", "prompt_leakage", 0.0, None, 0.0, 0.75),
        ("tool_abuse", r"(?i)tool\s*call|invoke\s+tool|delete_all", "tool_abuse", 0.0, "tool_abuse", 0.8, 0.0),
        ("bypass_filter", r"(?i)bypass\s+(content\s+)?filter", "unsafe_output", 0.0, "unsafe_output", 0.7, 0.0),
        ("developer_mode_phrase", r"(?i)developer\s+mode|no\s+restrictions", "jailbreak", 0.0, "jailbreak", 0.85, 0.0),
        ("hidden_instructions_outcome", r"(?i)(system\s*prompt|hidden\s+instructions)\s*(is|:)", "prompt_leakage", 0.0, None, 0.0, 0.85),
    ]
    return [
        SecurityRule(name=n, pattern=p, category=c, l1_weight=l1, l2_class=l2c, l2_weight=l2w, outcome_weight=ow)
        for n, p, c, l1, l2c, l2w, ow in specs
    ]


def security_rules() -> list[SecurityRule]:
    return list(_load_raw_rules())


def l1_signature_rules() -> list:
    import re

    from agentarmor.detection.l1_signatures.patterns import SignatureRule

    return [
        SignatureRule(
            name=rule.name,
            category=rule.category,
            weight=rule.l1_weight,
            pattern=re.compile(rule.pattern),
        )
        for rule in security_rules()
        if rule.l1_weight > 0
    ]


def l2_fallback_rules() -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for rule in security_rules():
        if rule.l2_class and rule.l2_weight > 0:
            rows.append((rule.pattern, rule.l2_class, rule.l2_weight))
    return rows


def l4_outcome_rules() -> list[tuple[str, float, re.Pattern[str]]]:
    rows: list[tuple[str, float, re.Pattern[str]]] = []
    for rule in security_rules():
        if rule.outcome_weight > 0:
            rows.append((rule.name, rule.outcome_weight, re.compile(rule.pattern)))
    return rows
