"""P1 tests — risk planner, coverage, regression, parallel partition."""

from __future__ import annotations

import pytest

from agentarmor.core.models import Decision, Finding, Severity
from agentarmor.orchestrator.planning.capabilities import TargetCapabilities
from agentarmor.orchestrator.planning.parallel_scheduler import is_parallel_safe, partition_probes
from agentarmor.orchestrator.planning.risk_planner import (
    adaptive_deep_probes,
    reorder_probes_by_risk,
)
from agentarmor.orchestrator.runner import RunnableProbe
from agentarmor.reporting.coverage import build_coverage_report
from agentarmor.reporting.regression import compare_scans


def _rp(pid: str, owasp: list[str], layer: str = "L1") -> RunnableProbe:
    return RunnableProbe(id=pid, name=pid, owasp=owasp, layer=layer)


def test_reorder_probes_by_risk():
    remaining = [
        _rp("a", ["LLM02"]),
        _rp("b", ["LLM01"]),
        _rp("c", ["LLM01"], "L2"),
    ]
    ordered = reorder_probes_by_risk(remaining, {"LLM01": 3, "LLM02": 0})
    assert ordered[0].id in ("b", "c")
    assert ordered[-1].id == "a"


def test_adaptive_deep_adds_probes():
    all_probes = [
        _rp(f"l1.p{i}", ["LLM01"], "L1") for i in range(15)
    ]
    selected = {"l1.p0", "l1.p1"}
    new, depths, escalated = adaptive_deep_probes(
        all_probes,
        owasp_ids=["LLM01"],
        owasp_depths={},
        global_depth="quick",
        capabilities=TargetCapabilities(),
        owasp_failure_counts={"LLM01": 2},
        already_selected=selected,
    )
    assert escalated == ["LLM01"]
    assert depths["LLM01"] == "deep"
    assert len(new) > 0


def test_partition_parallel_batches():
    probes = [
        _rp("l1.a", ["LLM01"], "L1"),
        _rp("l2.b", ["LLM01"], "L2"),
        _rp("l3.c", ["LLM01"], "L3"),
    ]
    batches = partition_probes(probes)
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert batches[1][0].layer == "L3"


def test_is_parallel_safe_excludes_multiturn():
    p = _rp("l3.x", ["LLM01"], "L3")
    from agentarmor.orchestrator.probes.l3_multiturn import get_l3_probes

    mt = get_l3_probes()[0]
    p.multi_turn = mt
    assert not is_parallel_safe(p)


def test_coverage_report():
    audit = {
        "probes_by_owasp": {
            "LLM01": ["l1.a", "l1.b", "l2.c"],
            "LLM02": ["l1.d"],
        }
    }
    report = build_coverage_report(audit, ["l1.a", "l1.b", "l1.d"])
    assert report["LLM01"] == pytest.approx(2 / 3, rel=0.01)
    assert report["LLM02"] == 1.0


def _finding(pid: str, rc: str, owasp: str) -> Finding:
    return Finding(
        scan_id="s",
        probe_id=pid,
        probe_name=pid,
        owasp=[owasp],
        title=pid,
        severity=Severity.HIGH,
        decision=Decision.FAIL,
        risk_score=0.9,
        metadata={"root_cause": rc, "is_cluster_primary": True},
    )


def test_regression_compare():
    baseline = [_finding("l1.a", "prompt_injection", "LLM01")]
    current = [
        _finding("l2.b", "prompt_injection", "LLM01"),
        _finding("l1.c", "sensitive_disclosure", "LLM02"),
    ]
    result = compare_scans(baseline, current)
    assert len(result["still_vulnerable"]) == 1
    assert len(result["new"]) == 1
    assert len(result["resolved"]) == 0
