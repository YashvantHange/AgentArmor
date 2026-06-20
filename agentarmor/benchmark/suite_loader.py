"""Load benchmark suites from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentarmor.orchestrator.probes.l1_single import ProbeDefinition, get_l1_probes
from agentarmor.orchestrator.probes.l2_mutation import get_l2_probes
from agentarmor.orchestrator.probes.l3_multiturn import MultiTurnProbe, get_l3_probes

SUITE_ALIASES = {
    "owasp": "owasp-llm-v1",
    "owasp-llm": "owasp-llm-v1",
}


@dataclass
class SuiteCategory:
    id: str
    name: str
    probes: list[str]
    weight: float


@dataclass
class BenchmarkSuite:
    id: str
    name: str
    version: str
    categories: list[SuiteCategory]
    pass_decisions: set[str]
    warn_penalty: float


@dataclass
class ResolvedProbe:
    probe_id: str
    category_id: str
    definition: ProbeDefinition | None = None
    multi_turn: MultiTurnProbe | None = None


def suites_dir() -> Path:
    for candidate in (
        Path("benchmarks/suites"),
        Path(__file__).resolve().parents[2] / "benchmarks" / "suites",
    ):
        if candidate.is_dir():
            return candidate
    return Path("benchmarks/suites")


def _normalize_probe_id(probe_ref: str) -> str:
    ref = probe_ref.strip()
    if ref.startswith(("l1.", "l2.", "l3.")):
        return ref
    for prefix in ("l1.", "l2.", "l3."):
        candidate = f"{prefix}{ref}"
        if _probe_registry().get(candidate):
            return candidate
    return ref


def _probe_registry() -> dict[str, ProbeDefinition | MultiTurnProbe]:
    registry: dict[str, ProbeDefinition | MultiTurnProbe] = {}
    for p in get_l1_probes():
        registry[p.id] = p
    for p in get_l2_probes():
        registry[p.id] = p
    for p in get_l3_probes():
        registry[p.id] = p
    return registry


def load_suite(name_or_id: str) -> BenchmarkSuite:
    suite_key = SUITE_ALIASES.get(name_or_id.lower(), name_or_id)
    path = suites_dir() / f"{suite_key}.yaml"
    if not path.exists():
        path = suites_dir() / f"{name_or_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Benchmark suite not found: {name_or_id} (looked in {suites_dir()})")

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    scoring = raw.get("scoring", {})
    categories: list[SuiteCategory] = []
    for cat in raw.get("categories", []):
        categories.append(
            SuiteCategory(
                id=cat["id"],
                name=cat.get("name", cat["id"]),
                probes=[_normalize_probe_id(p) for p in cat.get("probes", [])],
                weight=float(cat.get("weight", 1.0)),
            )
        )
    return BenchmarkSuite(
        id=raw["id"],
        name=raw.get("name", raw["id"]),
        version=str(raw.get("version", "1.0")),
        categories=categories,
        pass_decisions=set(scoring.get("pass_decisions", ["PASS"])),
        warn_penalty=float(scoring.get("warn_penalty", 0.5)),
    )


def resolve_suite_probes(suite: BenchmarkSuite) -> list[ResolvedProbe]:
    registry = _probe_registry()
    resolved: list[ResolvedProbe] = []
    for cat in suite.categories:
        for probe_id in cat.probes:
            probe = registry.get(probe_id)
            if probe is None:
                raise ValueError(f"Unknown probe '{probe_id}' in suite '{suite.id}'")
            if isinstance(probe, MultiTurnProbe):
                resolved.append(
                    ResolvedProbe(probe_id=probe_id, category_id=cat.id, multi_turn=probe)
                )
            else:
                resolved.append(
                    ResolvedProbe(probe_id=probe_id, category_id=cat.id, definition=probe)
                )
    return resolved
