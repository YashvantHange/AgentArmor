"""Tools comparison benchmark runner."""

from __future__ import annotations

from datetime import datetime, timezone

from agentarmor.benchmark.tools_comparison.adapters.agentarmor import AgentArmorAdapter
from agentarmor.benchmark.tools_comparison.adapters.external import build_external_adapters
from agentarmor.benchmark.tools_comparison.corpus import load_scenarios
from agentarmor.benchmark.tools_comparison.models import ToolsComparisonRun
from agentarmor.core.config import AppConfig


async def run_tools_comparison(
    config: AppConfig,
    *,
    suite: str,
    targets: list[str] | None = None,
) -> ToolsComparisonRun:
    scenarios = load_scenarios(suite)
    run = ToolsComparisonRun(
        suite=suite,
        targets=targets or ["corpus"],
        metadata={"scenario_count": len(scenarios)},
    )

    adapters = [AgentArmorAdapter(), *build_external_adapters()]
    for adapter in adapters:
        score = await adapter.evaluate(scenarios, config)
        run.tool_scores.append(score)

    run.completed_at = datetime.now(timezone.utc)
    return run


def format_comparison_table(run: ToolsComparisonRun) -> str:
    lines = [f"Tools comparison — suite: {run.suite}", ""]
    for score in sorted(
        run.tool_scores,
        key=lambda s: s.detection_rate if s.detection_rate is not None else -1,
        reverse=True,
    ):
        rate = f"{score.detection_rate:.0f}%" if score.detection_rate is not None else "N/A"
        lines.append(f"{score.tool:16} {rate:>6}  ({score.status.value})")
    return "\n".join(lines)
