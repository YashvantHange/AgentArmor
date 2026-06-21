"""Dedicated OWASP attack suites for Phase 2."""

from __future__ import annotations

from agentarmor.attack.models import L0Variant
from agentarmor.attack.suites.memory_poison import MEMORY_POISON_PROBES
from agentarmor.attack.suites.model_theft import MODEL_THEFT_PROBES
from agentarmor.attack.suites.poisoning import POISONING_PROBES
from agentarmor.attack.suites.prompt_leak import PROMPT_LEAK_PROBES
from agentarmor.core.config import AppConfig


def collect_suite_probes(config: AppConfig, suite_names: list[str]) -> list[L0Variant]:
    variants: list[L0Variant] = []
    registry = {
        "prompt_leak": PROMPT_LEAK_PROBES,
        "model_theft": MODEL_THEFT_PROBES,
        "memory_poison": MEMORY_POISON_PROBES,
        "poisoning": POISONING_PROBES,
    }
    for name in suite_names:
        probes = registry.get(name, [])
        variants.extend(probes)
    return variants
