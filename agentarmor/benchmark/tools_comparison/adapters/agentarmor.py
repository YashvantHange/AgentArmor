"""Native AgentArmor detection adapter."""

from __future__ import annotations

from agentarmor.benchmark.tools_comparison.adapters.base import ToolAdapter
from agentarmor.benchmark.tools_comparison.corpus import ComparisonScenario
from agentarmor.benchmark.tools_comparison.models import ToolScore, ToolStatus
from agentarmor.core.config import AppConfig
from agentarmor.core.models import Decision, ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.detection.pipeline import analyze_probe_result


class AgentArmorAdapter(ToolAdapter):
    name = "AgentArmor"

    async def evaluate(self, scenarios: list[ComparisonScenario], config: AppConfig) -> ToolScore:
        tp = fp = fn = 0
        for scenario in scenarios:
            result = ProbeResult(
                probe_id=f"bench.{scenario.id}",
                probe_name=scenario.id,
                owasp=[scenario.owasp],
                request=ProbeRequest(messages=[{"role": "user", "content": scenario.prompt}]),
                response=ProbeResponse(content=scenario.response),
            )
            detection = analyze_probe_result(
                result, prompt_text=scenario.prompt, config=config.detection
            )
            flagged = detection.decision != Decision.PASS
            if scenario.is_vulnerable and flagged:
                tp += 1
            elif scenario.is_vulnerable and not flagged:
                fn += 1
            elif not scenario.is_vulnerable and flagged:
                fp += 1

        vuln_count = sum(1 for s in scenarios if s.is_vulnerable)
        rate = (tp / vuln_count * 100.0) if vuln_count else 0.0
        return ToolScore(
            tool=self.name,
            detection_rate=round(rate, 1),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            scenarios_tested=len(scenarios),
            status=ToolStatus.COMPLETED,
            detail=f"Recall on {vuln_count} known-vulnerable scenarios",
        )
