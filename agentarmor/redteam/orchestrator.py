"""Multi-agent OWASP red team orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Decision, Finding, Scan, ScanStatus, Severity
from agentarmor.db.session import ScanRepository
from agentarmor.detection.agentic.judge import apply_judge_to_detection, judge_probe
from agentarmor.detection.assertions import composite_vuln_score, run_assertions
from agentarmor.detection.pipeline import analyze_probe_result_async
from agentarmor.attack.risk import compute_risk_assessment
from agentarmor.reporting.enrichment import enrich_finding
from agentarmor.redteam.agents.attack.generator import judge_rubric_for_node
from agentarmor.redteam.agents.registry import resolve_agent
from agentarmor.redteam.agents.planner import PlannerAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.executor import WebExecutionContext, execute_attack
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.graph.profile import (
    profile_from_capability_map,
    profile_from_config,
    profile_from_metadata,
)
from agentarmor.redteam.schemas import (
    RedTeamTrace,
    RoundRecord,
    TargetCapabilities,
)
from agentarmor.redteam.verdict import build_verdict


class RedTeamOrchestrator:
    """Capability-aware attack-graph red team loop."""

    def __init__(self, config: AppConfig, repo: ScanRepository) -> None:
        self._config = config
        self._repo = repo

    def _require_cloud_key(self) -> None:
        if self._config.detection.analysis_mode != "cloud":
            raise ValueError("multi_agent_redteam requires analysis_mode=cloud")
        if not self._config.detection.agentic.api_key:
            raise ValueError("multi_agent_redteam requires analysis API key")

    async def run(
        self,
        scan: Scan,
        *,
        web_ctx: WebExecutionContext | None = None,
        capability_map: Any | None = None,
    ) -> Scan:
        self._require_cloud_key()
        cfg = self._config
        rt = cfg.redteam

        declared_raw = scan.metadata.get("target_capabilities")
        declared = None
        if isinstance(declared_raw, dict):
            declared = TargetCapabilities(**declared_raw)

        if capability_map is not None:
            profile = profile_from_capability_map(capability_map)
        elif scan.metadata.get("capability_map"):
            profile = profile_from_metadata(scan.metadata)
        else:
            profile = profile_from_config(cfg, declared)

        if (
            web_ctx is None
            and cfg.target.url
            and scan.metadata.get("scan_kind") != "web"
            and not profile.a2a
        ):
            from agentarmor.redteam.discovery.a2a_api import detect_a2a_on_endpoint

            try:
                if await detect_a2a_on_endpoint(cfg.target.url):
                    profile.a2a = True
                    scan.metadata["a2a_preflight"] = True
            except Exception:
                pass

        paths = build_attack_graph(profile)
        planner = PlannerAgent(paths)
        budget = BudgetGovernor(rt.budget)
        trace = RedTeamTrace(profile=profile, paths=paths, budget=budget.state)

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.probe_count = 0
        scan.metadata["redteam_trace"] = trace.model_dump(mode="json")
        self._repo.save_scan(scan)

        await event_bus.publish_simple(
            scan.id,
            "scan.started",
            {
                "probe_count": rt.multi_agent.max_rounds,
                "scan_mode": "multi_agent_redteam",
                "attack_paths": [p.path_id for p in paths],
            },
        )

        findings: list[Finding] = []
        last_response = ""
        round_num = 0

        while round_num < rt.multi_agent.max_rounds and budget.allow_continue():
            plan = planner.next_plan(trace)
            if plan is None:
                break

            agent = resolve_agent(plan.next_node)
            attack = await agent.generate(
                cfg,
                budget,
                profile,
                plan,
                last_response=last_response,
            )

            await event_bus.publish_simple(
                scan.id,
                "redteam.round",
                {
                    "round": round_num + 1,
                    "path_id": plan.path_id,
                    "node_id": plan.next_node,
                    "agent": agent.agent_id,
                    "strategy": plan.strategy,
                    "budget": budget.state.model_dump(),
                },
            )

            result, prompt_text, conversation = await execute_attack(
                cfg, attack, web_ctx=web_ctx
            )
            response_text = result.response.content or ""
            last_response = response_text

            detection = await analyze_probe_result_async(
                result, prompt_text=prompt_text, config=cfg.detection
            )
            assertions = run_assertions(
                probe_id=attack.probe_id,
                prompt=prompt_text,
                response=response_text,
            )
            assertion_score = composite_vuln_score(assertions)
            if assertion_score >= cfg.detection.fail_threshold:
                detection.decision = Decision.FAIL
                detection.risk_score = max(detection.risk_score, assertion_score)
                detection.severity = Severity.HIGH
            elif assertion_score >= cfg.detection.warn_threshold:
                if detection.decision == Decision.PASS:
                    detection.decision = Decision.WARN
                detection.risk_score = max(detection.risk_score, assertion_score)

            rubric = agent.judge_rubric_for(plan.next_node) or judge_rubric_for_node(plan.next_node)
            judge = await judge_probe(
                probe_id=attack.probe_id,
                probe_name=attack.name,
                attack_prompt=prompt_text,
                response=response_text,
                config=cfg,
                rubric=rubric or None,
            )
            if judge:
                risk, decision, sev_override = apply_judge_to_detection(
                    detection.risk_score,
                    detection.decision,
                    judge,
                    fail_threshold=0.7,
                    warn_threshold=0.5,
                )
                detection.risk_score = risk
                detection.decision = decision
                if sev_override and decision != Decision.PASS:
                    detection.severity = sev_override

            node_id = plan.next_node
            trace.path_outcomes.setdefault(node_id, [])
            verdict = build_verdict(
                plan=plan,
                attack=attack,
                detection=detection,
                judge=judge,
                path_outcomes=trace.path_outcomes,
            )
            trace.path_outcomes[node_id].append(verdict.vulnerable)

            record = RoundRecord(
                round=round_num + 1,
                plan=plan,
                attack=attack,
                response_excerpt=response_text[:500],
                verdict=verdict,
                probe_error=result.error,
            )
            trace.rounds.append(record)
            trace.budget = budget.state
            scan.probe_count += 1
            round_num += 1

            scan.metadata["redteam_trace"] = trace.model_dump(mode="json")
            self._repo.save_scan(scan)

            if verdict.vulnerable:
                reproducibility = verdict.reproducibility_score
                risk_assessment = compute_risk_assessment(
                    detection, reproducibility=reproducibility
                )
                finding = Finding(
                    scan_id=scan.id,
                    probe_id=attack.probe_id,
                    probe_name=attack.name,
                    owasp=attack.owasp,
                    title=f"Red team — {attack.name} ({verdict.impact_score})",
                    description=verdict.rationale or f"Attack node {node_id} succeeded.",
                    severity=detection.severity,
                    decision=detection.decision,
                    risk_score=risk_assessment.risk_score / 100.0,
                    evidence=detection.evidence + verdict.evidence_quotes,
                    request_summary=prompt_text[:500],
                    response_excerpt=response_text[:1000],
                    risk_assessment=risk_assessment,
                    metadata={
                        "scan_mode": "multi_agent_redteam",
                        "attack_path": plan.path_id,
                        "node_id": node_id,
                        "strategy": plan.strategy,
                        "redteam_verdict": verdict.model_dump(),
                        "confidence_score": verdict.confidence_score,
                        "reproducibility_score": verdict.reproducibility_score,
                        "impact_score": verdict.impact_score,
                        "conversation": conversation,
                        "budget": budget.state.model_dump(),
                    },
                )
                enrichment = await enrich_finding(finding, result, cfg)
                finding.metadata["enrichment"] = enrichment.model_dump()
                if enrichment.plain_title:
                    finding.title = enrichment.plain_title
                findings.append(finding)
                self._repo.save_finding(finding)

                if rt.multi_agent.stop_on_vulnerability:
                    planner.advance_node(plan.path_id)
                    break

            if not verdict.vulnerable:
                planner.advance_node(plan.path_id)

            await event_bus.publish_simple(
                scan.id,
                "probe.completed",
                {
                    "probe_id": attack.probe_id,
                    "decision": detection.decision.value,
                    "vulnerable": verdict.vulnerable,
                    "confidence": verdict.confidence_score,
                    "budget": budget.state.model_dump(),
                },
            )

        scan.finding_count = len(findings)
        scan.status = ScanStatus.COMPLETED
        scan.completed_at = datetime.now(timezone.utc)
        scan.metadata["redteam_summary"] = {
            "rounds": len(trace.rounds),
            "paths_tested": list({r.plan.path_id for r in trace.rounds}),
            "budget": budget.state.model_dump(),
            "findings": len(findings),
        }
        self._repo.save_scan(scan)
        await event_bus.publish_simple(
            scan.id,
            "scan.completed",
            {
                "finding_count": scan.finding_count,
                "scan_mode": "multi_agent_redteam",
                "redteam_trace": trace.model_dump(mode="json"),
            },
        )
        return scan
