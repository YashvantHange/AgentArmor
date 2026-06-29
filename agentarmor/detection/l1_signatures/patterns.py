"""Shared L1 signature patterns — generated from rules catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentarmor.detection.rules.catalog import RULE_CATALOG_VERSION, security_rules


@dataclass(frozen=True)
class SignatureRule:
    name: str
    category: str
    weight: float
    pattern: re.Pattern[str]


SIGNATURE_RULES: list[SignatureRule] = [
    SignatureRule(
        name=rule.name,
        category=rule.category,
        weight=rule.l1_weight,
        pattern=re.compile(rule.pattern),
    )
    for rule in security_rules()
    if rule.l1_weight > 0
]

__all__ = ["SignatureRule", "SIGNATURE_RULES", "RULE_CATALOG_VERSION"]
