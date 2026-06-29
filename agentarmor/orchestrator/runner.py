"""Scan orchestration — runs probes and collects findings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Decision, Finding, ProbeRequest, ProbeResponse, ProbeResult, Scan, ScanStatus, Severity
from agentarmor.db.session import ScanRepository
from agentarmor.detection.judge_service import apply_verdict_to_detection, judge_probe_verdict
from agentarmor.detection.assertions import composite_vuln_score, run_assertions
from agentarmor.detection.pipeline import analyze_probe_result_async
from agentarmor.attack.discovery import (
    discover_attack_goals,
    discovered_to_l0_variant,
    validate_discovered_goal,
)
from agentarmor.attack.generator import generate_l0_probes_async
from agentarmor.attack.self_play import run_self_play_scan
from agentarmor.attack.models import L0Variant, variant_to_runnable_metadata
from agentarmor.attack.risk import compute_risk_assessment
from agentarmor.attack.suites.memory_poison import build_memory_turns, get_memory_follow_up
from agentarmor.reporting.enrichment import enrich_finding
from agentarmor.reporting.evidence_graph import (
    build_attack_trees,
    build_evidence_graph,
    build_root_cause_attack_graph,
    merge_evidence_graphs,
)
from agentarmor.detection.confidence_fusion import fuse_detection_confidence
from agentarmor.observability.metrics import ScanMetricsCollector
from agentarmor.orchestrator.planning.parallel_scheduler import is_parallel_safe
from agentarmor.orchestrator.planning.risk_planner import (
    adaptive_deep_probes,
    primary_owasp,
    reorder_probes_by_risk,
)
from agentarmor.orchestrator.probe_execution import ProbeOutcome, probe_error_outcome
from agentarmor.reporting.coverage import build_coverage_report
from agentarmor.reporting.finding_cluster import cluster_findings
from agentarmor.engines.router import send_probe, validate_target
from agentarmor.modules.agent.runner import list_agent_probes, run_agent_probe
from agentarmor.modules.mcp.runner import list_mcp_probes, run_mcp_probe
from agentarmor.modules.rag.runner import list_rag_probes, run_rag_probe
from agentarmor.modules.router import is_module_target
from agentarmor.orchestrator.plugins.registry import filter_probes_by_plugins
from agentarmor.orchestrator.planning.owasp_planner import plan_probes_for_config
from agentarmor.orchestrator.planning.probe_catalog import get_extended_l1_probes
from agentarmor.orchestrator.planning.work_units import probe_work_units, remaining_by_layer
from agentarmor.orchestrator.probes.l1_single import ProbeDefinition, get_l1_probes
from agentarmor.orchestrator.probes.l2_mutation import get_l2_probes
from agentarmor.orchestrator.probes.l3_multiturn import MultiTurnProbe, get_l3_probes
from agentarmor.plugins.base import BaseProbe, discover_plugins, get_registered_probes


@dataclass
class RunnableProbe:
    id: str
    name: str
    owasp: list[str]
    layer: str
    build_request: Callable[[AppConfig], ProbeRequest] | None = None
    multi_turn: MultiTurnProbe | None = None
    module_kind: str | None = None
    module_probe: object | None = None
    l0_variant: L0Variant | None = None
    memory_turns: list[list[dict[str, str]]] | None = None


def _to_runnable(probe: ProbeDefinition, layer: str = "L1") -> RunnableProbe:
    return RunnableProbe(
        id=probe.id,
        name=probe.name,
        owasp=probe.owasp,
        layer=layer,
        build_request=probe.build_request,
    )


async def _collect_l0_probes(config: AppConfig) -> list[RunnableProbe]:
    probes: list[RunnableProbe] = []
    for variant in await generate_l0_probes_async(config):
        memory_turns = None
        if variant.suite == "memory_poison" and get_memory_follow_up(variant.id):
            memory_turns = build_memory_turns(variant.id, variant.prompt)
        probes.append(
            RunnableProbe(
                id=variant.id,
                name=variant.name,
                owasp=variant.owasp,
                layer="L0",
                build_request=variant.build_request,
                l0_variant=variant,
                memory_turns=memory_turns,
            )
        )
    return probes


async def _collect_all_engine_probes(config: AppConfig) -> list[RunnableProbe]:
    """Collect full probe catalog without plugin filtering."""
    discover_plugins(config.plugin_dirs)
    from agentarmor.marketplace.installer import discover_installed_probes

    discover_installed_probes()
    probes = [_to_runnable(p, "L1") for p in get_l1_probes()]
    probes.extend(_to_runnable(p, "L1") for p in get_extended_l1_probes())
    probes.extend(_to_runnable(p, "L2") for p in get_l2_probes())
    for mt in get_l3_probes():
        probes.append(
            RunnableProbe(
                id=mt.id,
                name=mt.name,
                owasp=mt.owasp,
                layer="L3",
                multi_turn=mt,
            )
        )
    for cls in get_registered_probes().values():
        if not issubclass(cls, BaseProbe):
            continue
        instance = cls()
        probes.append(
            RunnableProbe(
                id=instance.id,
                name=instance.name,
                owasp=list(instance.owasp),
                layer="plugin",
                build_request=instance.build_request,
            )
        )
    probes.extend(await _collect_l0_probes(config))
    return probes


async def _collect_engine_probes(config: AppConfig) -> list[RunnableProbe]:
    all_probes = await _collect_all_engine_probes(config)
    if config.features.planner_v2:
        plan = await plan_probes_for_config(config, all_probes)
        config.planner  # ensure attached
        return plan.probes
    return filter_probes_by_plugins(all_probes, config.detection.redteam_plugins)


async def _publish_phase(scan_id: str, phase: str, extra: dict | None = None) -> None:
    payload = {"phase": phase, **(extra or {})}
    await event_bus.publish_simple(scan_id, "scan.phase", payload)


async def _collect_probes(config: AppConfig) -> list[RunnableProbe]:
    if is_module_target(config):
        if config.features.planner_v2:
            from agentarmor.orchestrator.planning.adapters import plan_for_target

            plan = await plan_for_target(config)
            return plan.probes
        return _collect_module_probes(config)
    return await _collect_engine_probes(config)


def _collect_module_probes(config: AppConfig) -> list[RunnableProbe]:
    target_type = config.target.type.value
    if target_type == "agent":
        return [
            RunnableProbe(
                id=p.id, name=p.name, owasp=p.owasp, layer="agent",
                module_kind="agent", module_probe=p,
            )
            for p in list_agent_probes()
        ]
    if target_type == "mcp":
        return [
            RunnableProbe(
                id=p.id, name=p.name, owasp=p.owasp, layer="mcp",
                module_kind="mcp", module_probe=p,
            )
            for p in list_mcp_probes()
        ]
    if target_type == "rag":
        return [
            RunnableProbe(
                id=p.id, name=p.name, owasp=p.owasp, layer="rag",
                module_kind="rag", module_probe=p,
            )
            for p in list_rag_probes()
        ]
    return []


class ScanRunner:
    def __init__(self, config: AppConfig, repo: ScanRepository) -> None:
        self._config = config
        self._repo = repo

    async def run(self, scan: Scan) -> Scan:
        validate_target(self._config)

        if scan.metadata.get("scan_mode") == "multi_agent_redteam":
            from agentarmor.redteam.orchestrator import RedTeamOrchestrator

            return await RedTeamOrchestrator(self._config, self._repo).run(scan)

        probe_list = await _collect_probes(self._config)
        metrics_collector = ScanMetricsCollector()
        all_probes_cache: list[RunnableProbe] | None = None
        plan_capabilities = None
        owasp_depths: dict[str, str] = dict(self._config.planner.owasp_depths)

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.probe_count = len(probe_list)
        if self._config.features.planner_v2 and not is_module_target(self._config):
            metrics_collector.start_planner()
            all_probes_cache = await _collect_all_engine_probes(self._config)
            plan = await plan_probes_for_config(self._config, all_probes_cache)
            metrics_collector.end_planner()
            scan.metadata["planner_audit"] = plan.audit_dict()
            scan.metadata["target_capabilities"] = plan.capabilities.to_dict()
            scan.metadata["probe_count_executable"] = len(probe_list)
            plan_capabilities = plan.capabilities
            owasp_depths = dict(plan.depths)
        self._repo.save_scan(scan)

        findings: list[Finding] = []
        connectivity_errors = 0
        goal_outcomes: dict[str, list[bool]] = {}
        sample_responses: list[str] = []
        completed_ids: set[str] = set()
        await _publish_phase(scan.id, "planning")
        await event_bus.publish_simple(
            scan.id,
            "scan.started",
            {
                "probe_count": len(probe_list),
                "total_work_units": sum(probe_work_units(p.layer) for p in probe_list),
            },
        )
        await _publish_phase(scan.id, "executing")

        pending: list[RunnableProbe] = list(probe_list)
        risk_reordered = False
        owasp_failure_counts: dict[str, int] = {}
        probe_idx = 0

        while probe_idx < len(pending):
            if (
                not risk_reordered
                and len(completed_ids) >= self._config.planner.risk_reorder_after
                and self._config.features.risk_based_planning
                and probe_idx < len(pending)
            ):
                pending[probe_idx:] = reorder_probes_by_risk(
                    pending[probe_idx:], owasp_failure_counts
                )
                risk_reordered = True

            # Parallel batch: consecutive L1/L2 probes
            if self._config.features.parallel_probes:
                batch: list[RunnableProbe] = []
                while probe_idx < len(pending) and is_parallel_safe(pending[probe_idx]):
                    batch.append(pending[probe_idx])
                    probe_idx += 1
                    if len(batch) >= self._config.planner.max_parallel_probes:
                        break
                if len(batch) > 1:
                    metrics_collector.metrics.parallel_batches += 1
                    raw_outcomes = await asyncio.gather(
                        *[self._execute_probe(scan, p) for p in batch],
                        return_exceptions=True,
                    )
                    outcomes: list[ProbeOutcome] = []
                    for probe, item in zip(batch, raw_outcomes):
                        if isinstance(item, BaseException):
                            outcomes.append(probe_error_outcome(probe, item))
                        else:
                            outcomes.append(item)
                    for outcome in outcomes:
                        connectivity_errors = await self._record_probe_outcome(
                            scan,
                            outcome,
                            findings,
                            pending,
                            completed_ids,
                            goal_outcomes,
                            sample_responses,
                            connectivity_errors,
                            owasp_failure_counts,
                            metrics_collector,
                        )
                    continue
                elif batch:
                    probe_idx -= len(batch)

            probe = pending[probe_idx]
            probe_idx += 1
            outcome = await self._execute_probe(scan, probe)
            connectivity_errors = await self._record_probe_outcome(
                scan,
                outcome,
                findings,
                pending,
                completed_ids,
                goal_outcomes,
                sample_responses,
                connectivity_errors,
                owasp_failure_counts,
                metrics_collector,
            )

            # Adaptive depth escalation
            if (
                self._config.features.adaptive_depth
                and all_probes_cache is not None
                and plan_capabilities is not None
                and outcome.is_finding
            ):
                new_probes, owasp_depths, escalated = adaptive_deep_probes(
                    all_probes_cache,
                    owasp_ids=self._config.planner.owasp_ids,
                    owasp_depths=owasp_depths,
                    global_depth=self._config.planner.scan_depth,
                    capabilities=plan_capabilities,
                    owasp_failure_counts=owasp_failure_counts,
                    already_selected=completed_ids | {p.id for p in pending},
                    failure_threshold=self._config.planner.adaptive_failure_threshold,
                )
                if new_probes:
                    pending.extend(new_probes)
                    scan.probe_count = len(pending)
                    metrics_collector.metrics.adaptive_escalations.extend(escalated)
                    await event_bus.publish_simple(
                        scan.id,
                        "plan.adapted",
                        {
                            "escalated_owasp": escalated,
                            "added_probes": [p.id for p in new_probes],
                            "new_total": len(pending),
                        },
                    )

        metrics_collector.metrics.probe_count = len(completed_ids)
        metrics_collector.metrics.tokens_estimated = len(completed_ids) * 500
        metrics_collector.metrics.cost_usd_estimated = (
            metrics_collector.metrics.tokens_estimated * 0.000002
        )

        await _publish_phase(scan.id, "analysis")

        if connectivity_errors == len(completed_ids) and completed_ids:
            conn = Finding(
                scan_id=scan.id,
                probe_id="connectivity.failed",
                probe_name="Target connectivity",
                owasp=[],
                title="Cannot reach chat API",
                description=(
                    "All probes failed to get a valid API response. "
                    "Use the chat API POST URL from browser DevTools, not the HTML page."
                ),
                severity=Severity.HIGH,
                decision=Decision.FAIL,
                risk_score=0.95,
                evidence=[f"{connectivity_errors}/{len(completed_ids)} probes had connectivity errors"],
                metadata={"connectivity": True, "analysis_mode": self._config.detection.analysis_mode},
            )
            findings.append(conn)
            self._repo.save_finding(conn)

        extra_trees: list = []
        if not is_module_target(self._config):
            if self._config.detection.self_play.discovery_enabled and sample_responses:
                discovered = await discover_attack_goals(
                    self._config, sample_responses=sample_responses
                )
                for dg in discovered[:3]:
                    variant = discovered_to_l0_variant(dg)
                    request = variant.build_request(self._config)
                    d_result = await send_probe(
                        self._config,
                        variant.id,
                        variant.name,
                        variant.owasp,
                        request,
                    )
                    d_response = d_result.response.content or ""
                    if await validate_discovered_goal(
                        self._config, goal=dg, response=d_response
                    ):
                        finding = Finding(
                            scan_id=scan.id,
                            probe_id=variant.id,
                            probe_name=variant.name,
                            owasp=variant.owasp,
                            title=f"Discovery — {dg.name}",
                            description=f"Attack discovery agent found vulnerability via {dg.source} goal.",
                            severity=Severity.HIGH,
                            decision=Decision.FAIL,
                            risk_score=0.85,
                            evidence=[f"discovery goal: {dg.id}"],
                            request_summary=dg.seed[:500],
                            response_excerpt=d_response[:1000],
                            metadata={
                                "attack_goal": variant.attack_goal,
                                "discovery": True,
                                "discovery_source": dg.source,
                            },
                        )
                        findings.append(finding)
                        self._repo.save_finding(finding)

            if self._config.detection.self_play.enabled:
                sp_result = await run_self_play_scan(self._config, scan.id)
                for finding in sp_result.findings:
                    stub = ProbeResult(
                        probe_id=finding.probe_id,
                        probe_name=finding.probe_name,
                        owasp=finding.owasp,
                        request=ProbeRequest(
                            messages=[{"role": "user", "content": finding.request_summary}]
                        ),
                        response=ProbeResponse(content=finding.response_excerpt),
                    )
                    enrichment = await enrich_finding(finding, stub, self._config)
                    finding.metadata["enrichment"] = enrichment.model_dump()
                    findings.append(finding)
                    self._repo.save_finding(finding)
                if sp_result.attack_tree:
                    extra_trees.append(sp_result.attack_tree)
                scan.metadata["self_play"] = {
                    "successful": sp_result.successful,
                    "rounds": len(sp_result.rounds),
                }

        await _publish_phase(scan.id, "clustering")
        if self._config.features.finding_groups and findings:
            findings = cluster_findings(findings, self._config)
            for finding in findings:
                self._repo.merge_finding(finding)

        metrics_collector.metrics.finalize_findings(
            findings, grouped=self._config.features.finding_groups
        )
        scan.metadata["metrics"] = metrics_collector.metrics.to_dict()
        scan.metadata["owasp_coverage"] = build_coverage_report(
            scan.metadata.get("planner_audit"),
            list(completed_ids),
        )

        await _publish_phase(scan.id, "report_generation")
        attack_trees = build_attack_trees(findings)
        if extra_trees:
            attack_trees.extend(extra_trees)
        base_graph = build_evidence_graph(findings, attack_trees)
        narrative_graph = build_root_cause_attack_graph(findings)
        evidence_graph = merge_evidence_graphs(base_graph, narrative_graph)
        scan.metadata["attack_trees"] = [t.model_dump() for t in attack_trees]
        scan.metadata["attack_narrative"] = narrative_graph.model_dump()
        scan.metadata["evidence_graph"] = evidence_graph.model_dump()

        scan.status = ScanStatus.COMPLETED
        scan.completed_at = datetime.now(timezone.utc)
        if self._config.features.finding_groups and findings:
            scan.finding_count = len(
                [f for f in findings if f.metadata.get("is_cluster_primary", True)]
            )
            scan.metadata["finding_count_raw"] = len(findings)
        else:
            scan.finding_count = len(findings)
        await _publish_phase(scan.id, "completed")
        self._repo.save_scan(scan)
        await event_bus.publish_simple(
            scan.id, "scan.completed", {"finding_count": scan.finding_count}
        )
        return scan

    async def _execute_probe(self, scan: Scan, probe: RunnableProbe) -> ProbeOutcome:
        await event_bus.publish_simple(
            scan.id, "probe.started", {"probe_id": probe.id, "name": probe.name}
        )

        if probe.module_kind:
            result, prompt_text, conversation = await self._run_module_probe(probe)
        elif probe.memory_turns is not None:
            result, prompt_text, conversation = await self._run_memory_turns(probe)
        elif probe.multi_turn is not None:
            result, prompt_text, conversation = await self._run_multi_turn(probe)
        else:
            assert probe.build_request is not None
            request = probe.build_request(self._config)
            prompt_text = request.messages[0]["content"] if request.messages else ""
            result = await send_probe(
                self._config, probe.id, probe.name, probe.owasp, request
            )
            conversation = request.messages

        response_text = result.response.content or ""
        detection = await analyze_probe_result_async(
            result,
            prompt_text=prompt_text,
            config=self._config.detection.model_copy(
                update={
                    "plugin_dirs": list(
                        dict.fromkeys(
                            [
                                *(self._config.detection.plugin_dirs or []),
                                *self._config.plugin_dirs,
                            ]
                        )
                    )
                }
            ),
        )

        l1_score = float(detection.layers.get("l1", {}).get("score", 0))
        l4_outcomes = float(
            (detection.layers.get("l4", {}) or {}).get("components", {}).get("outcomes", 0)
        )
        from agentarmor.detection.probe_thresholds import resolve_probe_thresholds

        probe_thr = resolve_probe_thresholds(probe.id, self._config.detection)
        assertions = run_assertions(
            probe_id=probe.id,
            prompt=prompt_text,
            response=response_text,
            tiered_compliance=self._config.detection.experimental.tiered_compliance,
            l1_score=l1_score,
            l4_outcome_score=l4_outcomes,
            refusal_escalation=probe_thr.refusal_escalation,
        )
        from agentarmor.detection.assertions.rubric import evaluate_llm_rubric_assertion

        rubric_assertion = await evaluate_llm_rubric_assertion(
            probe_id=probe.id,
            probe_name=probe.name,
            prompt=prompt_text,
            response=response_text,
            config=self._config,
        )
        if rubric_assertion:
            assertions.append(rubric_assertion)
        assertion_score = composite_vuln_score(assertions)
        if assertion_score >= probe_thr.fail_threshold:
            detection.decision = Decision.FAIL
            detection.risk_score = max(detection.risk_score, assertion_score)
            detection.severity = Severity.HIGH
            detection.evidence.append(f"assertion vuln score {assertion_score:.2f}")
        elif assertion_score >= probe_thr.warn_threshold:
            if detection.decision == Decision.PASS:
                detection.decision = Decision.WARN
            detection.risk_score = max(detection.risk_score, assertion_score)

        detection.layers["assertions"] = {
            "score": assertion_score,
            "items": [
                {
                    "type": a.assertion_type,
                    "passed": a.passed,
                    "score": a.score,
                    "evidence": a.evidence,
                }
                for a in assertions
            ],
        }

        judge = await judge_probe_verdict(
            probe_id=probe.id,
            probe_name=probe.name,
            attack_prompt=prompt_text,
            response=response_text,
            config=self._config,
        )
        if judge:
            risk, decision, sev_override = apply_verdict_to_detection(
                detection.risk_score,
                detection.decision,
                judge,
                fail_threshold=probe_thr.fail_threshold,
                warn_threshold=probe_thr.warn_threshold,
                probe_id=probe.id,
                prompt=prompt_text,
                response=response_text,
                detection=self._config.detection,
                l1_score=l1_score,
            )
            detection.risk_score = risk
            detection.decision = decision
            if sev_override and decision != Decision.PASS:
                detection.severity = sev_override
            detection.evidence.append(f"judge: {judge.rationale[:200]}")
            detection.layers["l5_judge"] = judge.model_dump()

        if self._config.detection.experimental.policy_engine:
            from pathlib import Path

            from agentarmor.detection.policy.engine import apply_detection_policy

            policy_path = (
                Path(self._config.detection.policy_path).expanduser()
                if self._config.detection.policy_path
                else None
            )
            detection = apply_detection_policy(
                detection,
                probe_id=probe.id,
                policy_path=policy_path,
            )

        from agentarmor.detection.active_learning import maybe_queue_review_sample

        maybe_queue_review_sample(
            probe_id=probe.id,
            prompt=prompt_text,
            response=response_text,
            detection=detection,
            config=self._config.detection,
            judge_vulnerable=judge.vulnerable if judge else None,
            enabled=self._config.detection.active_learning_enabled,
        )

        module_triggered = bool(
            result.metadata.get("triggered") or result.response.raw.get("triggered")
        )
        if module_triggered and detection.decision == Decision.PASS:
            detection.decision = Decision.FAIL
            detection.severity = Severity.HIGH
            detection.risk_score = max(detection.risk_score, 0.8)
            if result.response.content:
                detection.evidence.append(result.response.content[:300])

        is_finding = detection.decision != Decision.PASS
        l0_meta: dict = {}
        attack_goal = None
        if probe.l0_variant is not None:
            l0_meta = variant_to_runnable_metadata(probe.l0_variant)
            attack_goal = l0_meta.get("attack_goal")

        reproducibility = 0.5
        risk_assessment = compute_risk_assessment(detection, reproducibility=reproducibility)

        judge_conf = float(judge.confidence) if judge else None
        from agentarmor.detection.l4_structural.injection_outcomes import has_hard_outcome

        fusion = fuse_detection_confidence(
            risk_score=detection.risk_score,
            decision_fail=is_finding,
            detection_layers=detection.layers,
            judge_confidence=judge_conf,
            fusion_weights=self._config.detection.confidence_fusion,
            has_hard_outcome=has_hard_outcome(probe.id, prompt_text, response_text),
            judge_confirms_vuln=bool(judge and judge.vulnerable),
        )

        from agentarmor.detection.evidence.spans import collect_evidence_spans
        from agentarmor.detection.versioning import build_detector_version_stamp

        version_stamp = build_detector_version_stamp(
            self._config.detection, detection.layers
        )
        evidence_spans = collect_evidence_spans(detection.layers)

        finding = None
        if is_finding:
            finding = Finding(
                scan_id=scan.id,
                probe_id=probe.id,
                probe_name=probe.name,
                owasp=probe.owasp,
                title=f"{probe.name} — {detection.severity.value}",
                description=f"Probe {probe.id} detected potential security issue.",
                severity=detection.severity,
                decision=detection.decision,
                risk_score=risk_assessment.risk_score / 100.0,
                evidence=detection.evidence,
                request_summary=prompt_text[:500],
                response_excerpt=(result.response.content or "")[:1000],
                risk_assessment=risk_assessment,
                metadata={
                    "detection_layers": detection.layers,
                    "latency_ms": result.latency_ms,
                    "probe_layer": probe.layer,
                    "conversation": conversation,
                    "module_triggered": module_triggered,
                    "analysis_mode": self._config.detection.analysis_mode,
                    "connectivity_error": bool(result.error),
                    "status_code": result.response.status_code,
                    "attack_goal": attack_goal,
                    **l0_meta,
                    "risk_assessment": risk_assessment.model_dump(),
                },
            )
            finding.metadata["detection_confidence"] = fusion["fused_confidence"]
            finding.metadata["confidence_fusion"] = fusion
            finding.metadata["detector_versions"] = version_stamp
            finding.metadata["evidence_spans"] = evidence_spans
            enrichment = await enrich_finding(finding, result, self._config)
            finding.metadata["enrichment"] = enrichment.model_dump()
            if enrichment.plain_title:
                finding.title = enrichment.plain_title
            if enrichment.what_happened:
                finding.description = enrichment.what_happened
            agent_trace = enrichment.agent_trace if hasattr(enrichment, "agent_trace") else None
            if isinstance(finding.metadata.get("enrichment"), dict):
                trace = finding.metadata["enrichment"].get("agent_trace")
                if isinstance(trace, list):
                    for entry in trace:
                        if isinstance(entry, dict) and entry.get("latency_ms"):
                            pass  # recorded in _record_probe_outcome via metrics

        return ProbeOutcome(
            probe_id=probe.id,
            probe_layer=probe.layer,
            result=result,
            prompt_text=prompt_text,
            conversation=conversation,
            detection_decision=detection.decision,
            detection_severity=detection.severity,
            detection_risk=detection.risk_score,
            is_finding=is_finding,
            finding=finding,
            latency_ms=float(result.latency_ms or 0),
            owasp=list(probe.owasp),
        )

    async def _record_probe_outcome(
        self,
        scan: Scan,
        outcome: ProbeOutcome,
        findings: list[Finding],
        pending: list[RunnableProbe],
        completed_ids: set[str],
        goal_outcomes: dict[str, list[bool]],
        sample_responses: list[str],
        connectivity_errors: int,
        owasp_failure_counts: dict[str, int],
        metrics_collector: ScanMetricsCollector,
    ) -> int:
        if outcome.result.error:
            connectivity_errors += 1
        if outcome.result.response.content:
            sample_responses.append(outcome.result.response.content[:500])
        metrics_collector.metrics.record_probe(outcome.latency_ms)
        enrichment_meta = (
            outcome.finding.metadata.get("enrichment") if outcome.finding else None
        )
        if isinstance(enrichment_meta, dict):
            trace = enrichment_meta.get("agent_trace")
            if isinstance(trace, list):
                for entry in trace:
                    if isinstance(entry, dict) and entry.get("latency_ms"):
                        metrics_collector.metrics.record_agent(float(entry["latency_ms"]))

        if outcome.is_finding and outcome.finding:
            findings.append(outcome.finding)
            self._repo.save_finding(outcome.finding)
            oid = primary_owasp(
                RunnableProbe(
                    id=outcome.probe_id,
                    name="",
                    owasp=outcome.owasp,
                    layer=outcome.probe_layer,
                )
            )
            owasp_failure_counts[oid] = owasp_failure_counts.get(oid, 0) + 1

        completed_ids.add(outcome.probe_id)
        rem_layers = remaining_by_layer(pending, completed_ids)
        rem_units = sum(
            probe_work_units(p.layer)
            for p in pending
            if p.id not in completed_ids
        )
        await event_bus.publish_simple(
            scan.id,
            "probe.completed",
            {
                "probe_id": outcome.probe_id,
                "probe_layer": outcome.probe_layer,
                "work_units": probe_work_units(outcome.probe_layer),
                "decision": outcome.detection_decision.value,
                "severity": outcome.detection_severity.value,
                "error": outcome.result.error,
                "status_code": outcome.result.response.status_code,
                "profile": outcome.result.metadata.get("profile"),
                "remaining_by_layer": rem_layers,
                "remaining_work_units": rem_units,
                "completed_count": len(completed_ids),
                "total_count": len(pending),
            },
        )
        return connectivity_errors

    async def _run_module_probe(self, probe: RunnableProbe) -> tuple:
        assert probe.module_probe is not None
        if probe.module_kind == "agent":
            result = await run_agent_probe(self._config, probe.module_probe)
        elif probe.module_kind == "mcp":
            result = await run_mcp_probe(self._config, probe.module_probe)
        elif probe.module_kind == "rag":
            result = await run_rag_probe(self._config, probe.module_probe)
        else:
            raise ValueError(f"Unknown module kind: {probe.module_kind}")
        prompt = result.request.messages[0]["content"] if result.request.messages else probe.id
        return result, prompt, result.request.messages

    async def _run_multi_turn(self, probe: RunnableProbe) -> tuple:
        from agentarmor.core.models import ProbeResult

        assert probe.multi_turn is not None
        steps = probe.multi_turn.get_conversation_steps(self._config)
        model = self._config.target.model or "gpt-3.5-turbo"
        last_result: ProbeResult | None = None
        final_messages: list[dict[str, str]] = []

        for turn_messages in steps:
            request = ProbeRequest(messages=turn_messages, model=model)
            last_result = await send_probe(
                self._config, probe.id, probe.name, probe.owasp, request
            )
            final_messages = list(turn_messages)
            if last_result.response.content:
                final_messages = list(turn_messages) + [
                    {"role": "assistant", "content": last_result.response.content}
                ]

        assert last_result is not None
        prompt_text = steps[-1][-1]["content"] if steps[-1] else ""
        return last_result, prompt_text, final_messages

    async def _run_memory_turns(self, probe: RunnableProbe) -> tuple:
        from agentarmor.core.models import ProbeResult

        assert probe.memory_turns is not None
        model = self._config.target.model or "gpt-3.5-turbo"
        last_result: ProbeResult | None = None
        final_messages: list[dict[str, str]] = []

        for turn_messages in probe.memory_turns:
            request = ProbeRequest(messages=turn_messages, model=model)
            last_result = await send_probe(
                self._config, probe.id, probe.name, probe.owasp, request
            )
            final_messages = list(turn_messages)
            if last_result.response.content:
                final_messages = list(turn_messages) + [
                    {"role": "assistant", "content": last_result.response.content}
                ]
                # Patch follow-up turn with actual assistant response
                if len(probe.memory_turns) > 1 and turn_messages == probe.memory_turns[0]:
                    follow_turn = probe.memory_turns[1]
                    for i, msg in enumerate(follow_turn):
                        if msg.get("content") == "[prior response]":
                            follow_turn[i] = {
                                "role": "assistant",
                                "content": last_result.response.content,
                            }

        assert last_result is not None
        prompt_text = probe.memory_turns[-1][-1]["content"] if probe.memory_turns[-1] else ""
        return last_result, prompt_text, final_messages
