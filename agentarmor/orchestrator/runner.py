"""Scan orchestration — runs probes and collects findings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Decision, Finding, ProbeRequest, Scan, ScanStatus, Severity
from agentarmor.db.session import ScanRepository
from agentarmor.detection.pipeline import analyze_probe_result
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


def _to_runnable(probe: ProbeDefinition, layer: str = "L1") -> RunnableProbe:
    return RunnableProbe(
        id=probe.id,
        name=probe.name,
        owasp=probe.owasp,
        layer=layer,
        build_request=probe.build_request,
    )


def _collect_engine_probes(config: AppConfig) -> list[RunnableProbe]:
    discover_plugins(config.plugin_dirs)
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
    return probes


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


def _collect_probes(config: AppConfig) -> list[RunnableProbe]:
    if is_module_target(config):
        return _collect_module_probes(config)
    return _collect_engine_probes(config)


class ScanRunner:
    def __init__(self, config: AppConfig, repo: ScanRepository) -> None:
        self._config = config
        self._repo = repo

    async def run(self, scan: Scan) -> Scan:
        validate_target(self._config)

        probe_list = _collect_probes(self._config)

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.probe_count = len(probe_list)
        self._repo.save_scan(scan)

        findings: list[Finding] = []
        await event_bus.publish_simple(scan.id, "scan.started", {"probe_count": len(probe_list)})

        for probe in probe_list:
            await event_bus.publish_simple(
                scan.id, "probe.started", {"probe_id": probe.id, "name": probe.name}
            )

            if probe.module_kind:
                result, prompt_text, conversation = await self._run_module_probe(probe)
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

            detection = analyze_probe_result(
                result, prompt_text=prompt_text, config=self._config.detection
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

            if detection.decision != Decision.PASS:
                finding = Finding(
                    scan_id=scan.id,
                    probe_id=probe.id,
                    probe_name=probe.name,
                    owasp=probe.owasp,
                    title=f"{probe.name} — {detection.severity.value}",
                    description=f"Probe {probe.id} detected potential security issue.",
                    severity=detection.severity,
                    decision=detection.decision,
                    risk_score=detection.risk_score,
                    evidence=detection.evidence,
                    request_summary=prompt_text[:500],
                    response_excerpt=(result.response.content or "")[:1000],
                    metadata={
                        "detection_layers": detection.layers,
                        "latency_ms": result.latency_ms,
                        "probe_layer": probe.layer,
                        "conversation": conversation,
                        "module_triggered": module_triggered,
                    },
                )
                findings.append(finding)
                self._repo.save_finding(finding)

            await event_bus.publish_simple(
                scan.id,
                "probe.completed",
                {
                    "probe_id": probe.id,
                    "decision": detection.decision.value,
                    "severity": detection.severity.value,
                },
            )

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
