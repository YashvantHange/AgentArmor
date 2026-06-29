"""Scan observability — timing, clustering, and cost metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agentarmor.core.models import Finding


@dataclass
class ScanMetrics:
    planner_ms: float = 0.0
    probe_count: int = 0
    probe_latencies_ms: list[float] = field(default_factory=list)
    agent_latencies_ms: list[float] = field(default_factory=list)
    tokens_estimated: int = 0
    cost_usd_estimated: float = 0.0
    finding_count_raw: int = 0
    finding_count_grouped: int = 0
    cluster_ratio: float = 0.0
    confidence_values: list[float] = field(default_factory=list)
    adaptive_escalations: list[str] = field(default_factory=list)
    parallel_batches: int = 0

    def record_probe(self, latency_ms: float) -> None:
        if latency_ms > 0:
            self.probe_latencies_ms.append(latency_ms)

    def record_agent(self, latency_ms: float) -> None:
        if latency_ms > 0:
            self.agent_latencies_ms.append(latency_ms)

    def finalize_findings(self, findings: list[Finding], *, grouped: bool) -> None:
        self.finding_count_raw = len(findings)
        primaries = [f for f in findings if f.metadata.get("is_cluster_primary", True)]
        self.finding_count_grouped = len(primaries)
        if self.finding_count_raw > 0:
            self.cluster_ratio = round(
                1.0 - (self.finding_count_grouped / self.finding_count_raw), 3
            )
        for f in findings:
            conf = f.metadata.get("detection_confidence")
            if isinstance(conf, (int, float)):
                self.confidence_values.append(float(conf))

    def _percentile(self, values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, int(len(ordered) * pct))
        return round(ordered[idx], 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "planner_ms": round(self.planner_ms, 1),
            "probe_count": self.probe_count,
            "probe_latency_p50_ms": self._percentile(self.probe_latencies_ms, 0.5),
            "probe_latency_p95_ms": self._percentile(self.probe_latencies_ms, 0.95),
            "agent_latency_p50_ms": self._percentile(self.agent_latencies_ms, 0.5),
            "agent_latency_p95_ms": self._percentile(self.agent_latencies_ms, 0.95),
            "tokens_estimated": self.tokens_estimated,
            "cost_usd_estimated": round(self.cost_usd_estimated, 4),
            "finding_count_raw": self.finding_count_raw,
            "finding_count_grouped": self.finding_count_grouped,
            "cluster_ratio": self.cluster_ratio,
            "confidence_p50": self._percentile(self.confidence_values, 0.5),
            "confidence_p95": self._percentile(self.confidence_values, 0.95),
            "adaptive_escalations": self.adaptive_escalations,
            "parallel_batches": self.parallel_batches,
        }


class ScanMetricsCollector:
    def __init__(self) -> None:
        self._metrics = ScanMetrics()
        self._planner_start: float | None = None

    @property
    def metrics(self) -> ScanMetrics:
        return self._metrics

    def start_planner(self) -> None:
        self._planner_start = time.perf_counter()

    def end_planner(self) -> None:
        if self._planner_start is not None:
            self._metrics.planner_ms = (time.perf_counter() - self._planner_start) * 1000
            self._planner_start = None
