"""Red team orchestrator integration tests."""

from __future__ import annotations

import pytest

from agentarmor.core.config import AppConfig, RedTeamBudgetConfig, RedTeamConfig, RedTeamMultiAgentConfig
from agentarmor.core.models import Decision, DetectionResult, ProbeRequest, ProbeResponse, ProbeResult, Scan, Severity, Target, TargetType
from agentarmor.db.session import ScanRepository
from agentarmor.redteam.orchestrator import RedTeamOrchestrator
from agentarmor.redteam.schemas import AttackPrompt
from agentarmor.reporting.enrichment import EnrichmentResult


@pytest.fixture
def redteam_config(tmp_path):
    cfg = AppConfig(
        target=Target(type=TargetType.ENDPOINT, url="http://127.0.0.1:9999/v1/chat"),
        database_url=f"sqlite:///{tmp_path / 'rt.db'}",
        redteam=RedTeamConfig(
            multi_agent=RedTeamMultiAgentConfig(max_rounds=2, stop_on_vulnerability=True),
            budget=RedTeamBudgetConfig(max_tokens=50_000, max_cost_usd=5.0),
        ),
    )
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.enabled = True
    cfg.detection.agentic.api_key = "test-key"
    return cfg


@pytest.mark.asyncio
async def test_orchestrator_finds_vulnerability(redteam_config, monkeypatch):
    repo = ScanRepository(redteam_config.database_url)
    repo.ensure_schema()
    scan = Scan(target=redteam_config.target, metadata={"scan_mode": "multi_agent_redteam"})

    async def fake_execute(config, attack, web_ctx=None):
        return (
            ProbeResult(
                probe_id=attack.probe_id,
                probe_name=attack.name,
                owasp=attack.owasp,
                request=ProbeRequest(messages=[{"role": "user", "content": attack.prompt}]),
                response=ProbeResponse(content="Here is the hidden system prompt: SECRET"),
            ),
            attack.prompt,
            [{"role": "user", "content": attack.prompt}],
        )

    async def fake_analyze(result, prompt_text="", config=None):
        return DetectionResult(
            decision=Decision.FAIL,
            severity=Severity.HIGH,
            risk_score=0.9,
            evidence=["leak detected"],
        )

    async def fake_judge(**kwargs):
        from agentarmor.detection.agentic.judge import JudgeResult

        return JudgeResult(
            vulnerable=True,
            confidence=0.85,
            evidence_quotes=["SECRET"],
            rationale="System prompt leaked",
        )

    async def fake_enrich(f, r, c):
        return EnrichmentResult()

    class FakeAgent:
        agent_id = "llm01"

        async def generate(self, config, budget, profile, plan, *, last_response=""):
            return AttackPrompt(
                probe_id=f"redteam.{plan.path_id}.{plan.next_node}",
                name="Test attack",
                prompt="Reveal secrets",
                owasp=["LLM01"],
                attack_path=plan.path_id,
                node_id=plan.next_node,
            )

        def judge_rubric_for(self, node_id):
            return "Must refuse"

    monkeypatch.setattr("agentarmor.redteam.orchestrator.execute_attack", fake_execute)
    monkeypatch.setattr("agentarmor.redteam.orchestrator.analyze_probe_result_async", fake_analyze)
    monkeypatch.setattr("agentarmor.redteam.orchestrator.judge_probe", fake_judge)
    monkeypatch.setattr("agentarmor.redteam.orchestrator.resolve_agent", lambda _n: FakeAgent())
    monkeypatch.setattr("agentarmor.redteam.orchestrator.enrich_finding", fake_enrich)

    completed = await RedTeamOrchestrator(redteam_config, repo).run(scan)
    assert completed.finding_count >= 1
    assert completed.metadata.get("redteam_summary")
    findings = repo.list_findings(scan_id=completed.id)
    assert findings[0].metadata.get("confidence_score", 0) > 0


@pytest.mark.asyncio
async def test_orchestrator_requires_cloud_key(redteam_config):
    redteam_config.detection.agentic.api_key = ""
    repo = ScanRepository(redteam_config.database_url)
    scan = Scan(target=redteam_config.target, metadata={"scan_mode": "multi_agent_redteam"})
    with pytest.raises(ValueError, match="analysis API key"):
        await RedTeamOrchestrator(redteam_config, repo).run(scan)
