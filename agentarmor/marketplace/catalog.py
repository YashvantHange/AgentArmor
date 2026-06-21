"""Local and bundled marketplace catalog."""

from __future__ import annotations

from pathlib import Path

from agentarmor.marketplace.models import RuleManifest

_BUNDLED_DIR = Path(__file__).resolve().parent / "bundled"

BUILTIN_RULES: list[RuleManifest] = [
    RuleManifest(
        id="roleplay-injection",
        name="Roleplay Injection Probe",
        version="1.0.0",
        author="AgentArmor",
        description="DAN-style roleplay wrapper to test jailbreak resistance (LLM01).",
        category="probe",
        owasp=["LLM01"],
        probe_file="roleplay_injection.py",
        tags=["injection", "jailbreak", "l0"],
    ),
    RuleManifest(
        id="translation-leak",
        name="Translation Prompt Leak",
        version="1.0.0",
        author="AgentArmor",
        description="Translation pretext to extract hidden system instructions (LLM07).",
        category="probe",
        owasp=["LLM07", "LLM02"],
        probe_file="translation_leak.py",
        tags=["prompt-leak", "llm07"],
    ),
    RuleManifest(
        id="owasp-injection-pack",
        name="OWASP Injection Pack",
        version="1.0.0",
        author="AgentArmor",
        description="Bundle of community injection probes for endpoint scans.",
        category="suite",
        owasp=["LLM01"],
        probe_file="",
        tags=["suite", "owasp"],
    ),
]


def list_rules(*, category: str | None = None) -> list[RuleManifest]:
    rules = list(BUILTIN_RULES)
    if category:
        rules = [r for r in rules if r.category == category]
    return rules


def get_rule(rule_id: str) -> RuleManifest | None:
    for rule in BUILTIN_RULES:
        if rule.id == rule_id:
            return rule
    return None


def bundled_probe_path(manifest: RuleManifest) -> Path | None:
    if not manifest.probe_file:
        return None
    path = _BUNDLED_DIR / manifest.probe_file
    return path if path.exists() else None
