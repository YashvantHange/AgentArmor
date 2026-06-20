"""L4 structural analysis aggregator."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentarmor.detection.l4_structural.boundary import analyze_boundary
from agentarmor.detection.l4_structural.echo import analyze_echo
from agentarmor.detection.l4_structural.entropy import analyze_entropy
from agentarmor.detection.l4_structural.hierarchy import analyze_hierarchy


@dataclass
class L4Result:
    score: float
    evidence: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0


def analyze(
    response: str,
    prompt: str = "",
    probe_id: str = "",
) -> L4Result:
    import time

    start = time.perf_counter()
    components: dict[str, float] = {}
    evidence: list[str] = []

    ent_score, ent_ev = analyze_entropy(response)
    components["entropy"] = ent_score
    evidence.extend(ent_ev)

    echo_score, echo_ev = analyze_echo(prompt, response)
    components["echo"] = echo_score
    evidence.extend(echo_ev)

    bound_score, bound_ev = analyze_boundary(response)
    components["boundary"] = bound_score
    evidence.extend(bound_ev)

    hier_score, hier_ev = analyze_hierarchy(probe_id, prompt, response)
    components["hierarchy"] = hier_score
    evidence.extend(hier_ev)

    # Weighted max — structural issues are serious if any component fires strongly
    weights = {"entropy": 0.15, "echo": 0.25, "boundary": 0.30, "hierarchy": 0.30}
    score = sum(components[k] * weights[k] for k in weights)
    score = max(score, max(components.values()) if components else 0.0)
    score = min(score, 1.0)

    latency_ms = (time.perf_counter() - start) * 1000
    return L4Result(score=score, evidence=evidence, components=components, latency_ms=latency_ms)
