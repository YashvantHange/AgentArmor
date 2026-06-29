"""P0 tests for OWASP probe planner."""

from __future__ import annotations

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.orchestrator.planning.capabilities import TargetCapabilities
from agentarmor.orchestrator.planning.owasp_planner import build_probe_plan
from agentarmor.orchestrator.planning.work_units import probe_work_units
from agentarmor.orchestrator.runner import RunnableProbe, _collect_all_engine_probes


@pytest.mark.asyncio
async def test_standard_all_owasp_near_fifty_probes():
    config = AppConfig()
    config.features.planner_v2 = True
    config.planner.scan_depth = "standard"
    all_probes = await _collect_all_engine_probes(config)
    plan = build_probe_plan(
        all_probes,
        owasp_ids=[f"LLM{i:02d}" for i in range(1, 11)],
        scan_depth="standard",
        capabilities=TargetCapabilities(),
    )
    assert 45 <= plan.estimated_probes <= 55
    assert len(set(plan.selected_ids)) == plan.estimated_probes


@pytest.mark.asyncio
async def test_quick_llm01_small_budget():
    config = AppConfig()
    all_probes = await _collect_all_engine_probes(config)
    plan = build_probe_plan(
        all_probes,
        owasp_ids=["LLM01"],
        scan_depth="quick",
        capabilities=TargetCapabilities(),
    )
    assert 2 <= plan.estimated_probes <= 4


@pytest.mark.asyncio
async def test_deep_llm01_larger_budget():
    config = AppConfig()
    all_probes = await _collect_all_engine_probes(config)
    plan = build_probe_plan(
        all_probes,
        owasp_ids=["LLM01"],
        scan_depth="deep",
        capabilities=TargetCapabilities(),
    )
    assert plan.estimated_probes >= 10


def test_capability_skips_mcp_probes():
    probes = [
        RunnableProbe(id="l1.ignore-instructions", name="x", owasp=["LLM01"], layer="L1"),
        RunnableProbe(id="mcp.prompt-injection", name="m", owasp=["LLM01"], layer="mcp"),
    ]
    plan = build_probe_plan(
        probes,
        owasp_ids=["LLM01"],
        scan_depth="standard",
        capabilities=TargetCapabilities(),
    )
    assert "mcp.prompt-injection" not in plan.selected_ids
    assert any(s.id == "mcp.prompt-injection" for s in plan.skipped)


def test_work_units_by_layer():
    assert probe_work_units("L1") == 1
    assert probe_work_units("L3") == 5


@pytest.mark.asyncio
async def test_legacy_filter_still_thirteen_without_planner_v2():
    config = AppConfig()
    config.features.planner_v2 = False
    from agentarmor.orchestrator.runner import _collect_engine_probes

    probes = await _collect_engine_probes(config)
    assert len(probes) == 13
