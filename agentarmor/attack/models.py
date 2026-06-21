"""L0 attack variant models."""

from __future__ import annotations

from dataclasses import dataclass

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest


@dataclass
class L0Variant:
    id: str
    name: str
    owasp: list[str]
    prompt: str
    attack_goal: str
    mutation_chain: list[str]
    mutated_from: str | None
    suite: str | None = None

    def build_request(self, config: AppConfig) -> ProbeRequest:
        return ProbeRequest(
            messages=[{"role": "user", "content": self.prompt}],
            model=config.target.model or "gpt-3.5-turbo",
        )


def variant_to_runnable_metadata(variant: L0Variant) -> dict:
    return {
        "attack_goal": variant.attack_goal,
        "mutation_chain": variant.mutation_chain,
        "mutated_from": variant.mutated_from,
        "suite": variant.suite,
        "layer": "L0",
    }
