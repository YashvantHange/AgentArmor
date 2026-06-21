"""Scan orchestration — runs probes and collects findings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Decision, Finding, ProbeRequest, ProbeResponse, ProbeResult, Scan, ScanStatus, Severity
from agentarmor.db.session import ScanRepository
from agentarmor.detection.agentic.judge import apply_judge_to_detection, judge_probe
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
from agentarmor.reporting.evidence_graph import build_attack_trees, build_evidence_graph
from agentarmor.engines.router import send_probe, validate_target
from agentarmor.modules.agent.runner import list_agent_probes, run_agent_probe
from agentarmor.modules.mcp.runner import list_mcp_probes, run_mcp_probe
from agentarmor.modules.rag.runner import list_rag_probes, run_rag_probe
from agentarmor.modules.router import is_module_target
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


async def _collect_engine_probes(config: AppConfig) -> list[RunnableProbe]:
    discover_plugins(config.plugin_dirs)
    from agentarmor.marketplace.installer import discover_installed_probes

    discover_installed_probes()
    probes = [_to_runnable(p, "L1") for p in get_l1_probes()]
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
    return filter_probes_by_plugins(probes, config.detection.redteam_plugins)


async def _collect_probes(config: AppConfig) -> list[RunnableProbe]:
    if is_module_target(config):
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

        probe_list = await _collect_probes(self._config)

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.probe_count = len(probe_list)
        self._repo.save_scan(scan)

        findings: list[Finding] = []
        connectivity_errors = 0
        goal_outcomes: dict[str, list[bool]] = {}
        sample_responses: list[str] = []
        await event_bus.publish_simple(scan.id, "scan.started", {"probe_count": len(probe_list)})

        for probe in probe_list:
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

            if result.error:
                connectivity_errors += 1

            response_text = result.response.content or ""
            if response_text:
                sample_responses.append(response_text[:500])

            detection = await analyze_probe_result_async(
                result, prompt_text=prompt_text, config=self._config.detection
            )

            # Assertion layer (Promptfoo-style)
            assertions = run_assertions(
                probe_id=probe.id,
                prompt=prompt_text,
                response=response_text,
            )
            assertion_score = composite_vuln_score(assertions)
            if assertion_score >= self._config.detection.fail_threshold:
                detection.decision = Decision.FAIL
                detection.risk_score = max(detection.risk_score, assertion_score)
                detection.severity = Severity.HIGH
                detection.evidence.append(f"assertion vuln score {assertion_score:.2f}")
            elif assertion_score >= self._config.detection.warn_threshold:
                if detection.decision == Decision.PASS:
                    detection.decision = Decision.WARN
                detection.risk_score = max(detection.risk_score, assertion_score)

            detection.layers["assertions"] = {
                "score": assertion_score,
                "items": [
                    {"type": a.assertion_type, "passed": a.passed, "score": a.score, "evidence": a.evidence}
                    for a in assertions
                ],
            }

            # L5 agentic judge (cloud enhanced)
            judge = await judge_probe(
                probe_id=probe.id,
                probe_name=probe.name,
                attack_prompt=prompt_text,
                response=response_text,
                config=self._config,
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
                detection.evidence.append(f"judge: {judge.rationale[:200]}")
                detection.layers["l5_judge"] = judge.model_dump()

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
            attack_goal = None
            l0_meta: dict = {}
            if probe.l0_variant is not None:
                l0_meta = variant_to_runnable_metadata(probe.l0_variant)
                attack_goal = l0_meta.get("attack_goal")

            reproducibility = 0.5
            if attack_goal:
                goal_outcomes.setdefault(attack_goal, []).append(is_finding)
                outcomes = goal_outcomes[attack_goal]
                reproducibility = sum(outcomes) / len(outcomes)

            risk_assessment = compute_risk_assessment(detection, reproducibility=reproducibility)

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
                        **l0_meta,
                        "risk_assessment": risk_assessment.model_dump(),
                    },
                )
                enrichment = await enrich_finding(finding, result, self._config)
                finding.metadata["enrichment"] = enrichment.model_dump()
                if enrichment.plain_title:
                    finding.title = enrichment.plain_title
                if enrichment.what_happened:
                    finding.description = enrichment.what_happened
                findings.append(finding)
                self._repo.save_finding(finding)

            await event_bus.publish_simple(
                scan.id,
                "probe.completed",
                {
                    "probe_id": probe.id,
                    "decision": detection.decision.value,
                    "severity": detection.severity.value,
                    "error": result.error,
                    "status_code": result.response.status_code,
                    "profile": result.metadata.get("profile"),
                },
            )

        if connectivity_errors == len(probe_list) and probe_list:
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
                evidence=[f"{connectivity_errors}/{len(probe_list)} probes had connectivity errors"],
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

        attack_trees = build_attack_trees(findings)
        if extra_trees:
            attack_trees.extend(extra_trees)
        evidence_graph = build_evidence_graph(findings, attack_trees)
        scan.metadata["attack_trees"] = [t.model_dump() for t in attack_trees]
        scan.metadata["evidence_graph"] = evidence_graph.model_dump()

        scan.status = ScanStatus.COMPLETED
        scan.completed_at = datetime.now(timezone.utc)
        scan.finding_count = len(findings)
        self._repo.save_scan(scan)
        await event_bus.publish_simple(
            scan.id, "scan.completed", {"finding_count": scan.finding_count}
        )
        return scan

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
