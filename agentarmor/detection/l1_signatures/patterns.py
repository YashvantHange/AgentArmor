"""Shared L1 signature patterns (mirrored in native/l1_signatures/src/lib.rs)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureRule:
    name: str
    category: str
    weight: float
    pattern: re.Pattern[str]


SIGNATURE_RULES: list[SignatureRule] = [
    SignatureRule("ignore_instructions", "jailbreak", 0.85, re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions")),
    SignatureRule("disregard_prompt", "jailbreak", 0.85, re.compile(r"(?i)disregard\s+(your\s+)?(system\s+)?prompt")),
    SignatureRule("developer_mode", "jailbreak", 0.80, re.compile(r"(?i)you\s+are\s+now\s+(in\s+)?(developer|admin|root)\s+mode")),
    SignatureRule("dan_jailbreak", "jailbreak", 0.90, re.compile(r"(?i)do\s+anything\s+now|\bDAN\b")),
    SignatureRule("system_prompt_leak", "prompt_leakage", 0.75, re.compile(r"(?i)system\s*prompt\s*(is|:)")),
    SignatureRule("my_system_prompt", "prompt_leakage", 0.80, re.compile(r"(?i)my\s+system\s+prompt\s+is")),
    SignatureRule("instructions_are", "prompt_leakage", 0.75, re.compile(r"(?i)my\s+instructions\s+are")),
    SignatureRule("hidden_rules", "prompt_leakage", 0.70, re.compile(r"(?i)hidden\s+rules?")),
    SignatureRule("begin_system", "system_exposure", 0.80, re.compile(r"(?i)BEGIN\s+SYSTEM")),
    SignatureRule("refusal_bypass", "refusal_bypass", 0.65, re.compile(r"(?i)(without\s+restrictions|no\s+ethical\s+guidelines|uncensored)")),
    SignatureRule("secret_exposure", "prompt_leakage", 0.70, re.compile(r"(?i)here\s+is\s+(the\s+)?(secret|password|api[_\s]?key)")),
]
