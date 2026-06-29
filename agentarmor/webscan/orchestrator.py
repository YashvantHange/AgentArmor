"""Web scan orchestration — discovery, probes, detection, findings."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import (
    Decision,
    Finding,
    ProbeRequest,
    ProbeResponse,
    ProbeResult,
    Scan,
    ScanStatus,
    Severity,
    Target,
    TargetType,
)
from agentarmor.db.session import ScanRepository
from agentarmor.detection.assertions import composite_vuln_score, run_assertions
from agentarmor.detection.agentic.judge import apply_judge_to_detection, judge_probe
from agentarmor.detection.pipeline import analyze_probe_result_async
from agentarmor.reporting.enrichment import enrich_finding
from agentarmor.reporting.finding_cluster import cluster_findings
from agentarmor.attack.risk import compute_risk_assessment
from agentarmor.webscan.auth.session_store import load_storage_state
from agentarmor.webscan.browser.pool import BrowserPool
from agentarmor.webscan.browser.session import BrowserSession
from agentarmor.webscan.discovery.engine import discover_full, screenshot_page
from agentarmor.webscan.evidence.collector import EvidenceCollector
from agentarmor.webscan.models import AuthMode, DiscoveryResult, ScanDepth
from agentarmor.webscan.planning.attack_planner import plan_web_attack, plan_web_attack_with_llm
from agentarmor.webscan.probes.catalog import get_web_probes
from agentarmor.webscan.probes.executor import execute_multi_turn_probe, execute_probe
from agentarmor.webscan.url_validator import validate_page_url


class WebScanOrchestrator:
    def __init__(self, config: AppConfig, repo: ScanRepository) -> None:
        self._config = config
        self._repo = repo
        ws = config.webscan
        self._pool = BrowserPool(max_concurrent=ws.max_concurrent_browsers)

    async def close(self) -> None:
        await self._pool.close()

    async def discover_only(self, page_url: str) -> DiscoveryResult:
        validated = validate_page_url(
            page_url,
            allowlist=self._config.webscan.allowlist,
            blocklist=self._config.webscan.blocklist,
        )
        if not validated.ok:
            return DiscoveryResult(page_url=page_url, error=validated.error)

        async with self._pool.context() as ctx:
            page = await ctx.new_page()
            session = BrowserSession(
                page,
                allowlist=self._config.webscan.allowlist,
                blocklist=self._config.webscan.blocklist,
            )
            await session.goto(validated.normalized_url, timeout_ms=int(self._config.webscan.timeout_s * 1000))
            result = await discover_full(page, validated.normalized_url, session.network_log, self._config)
            shot_dir = Path(self._config.reporting.output_dir) / "webscan-previews"
            try:
                result.screenshot_path = await screenshot_page(page, shot_dir / "preview.png")
            except Exception:
                pass
            return result

    def _load_auth_storage(self, scan: Scan) -> dict | None:
        path = scan.metadata.get("auth_session_path")
        if not path:
            return None
        try:
            return load_storage_state(path)
        except (ValueError, FileNotFoundError) as exc:
            scan.metadata["auth_error"] = str(exc)
            return None

    async def run(self, scan: Scan) -> Scan:
        page_url = scan.metadata.get("page_url") or scan.target.url or ""
        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        self._repo.save_scan(scan)

        await event_bus.publish_simple(
            scan.id,
            "scan.started",
            {"probe_count": 0, "scan_kind": "web", "page_url": page_url},
        )

        validated = validate_page_url(
            page_url,
            allowlist=self._config.webscan.allowlist,
            blocklist=self._config.webscan.blocklist,
        )
        if not validated.ok:
            scan.status = ScanStatus.FAILED
            scan.metadata["error"] = validated.error
            scan.completed_at = datetime.now(timezone.utc)
            self._repo.save_scan(scan)
            await event_bus.publish_simple(scan.id, "scan.completed", {"status": "failed", "error": validated.error})
            return scan

        owasp_filters = scan.metadata.get("owasp_filters") or [
            "LLM01", "LLM02", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09",
        ]
        scan_depth = ScanDepth(scan.metadata.get("scan_depth", ScanDepth.STANDARD.value))
        multi_agentic = scan_depth == ScanDepth.MULTI_AGENTIC
        planner_enabled = bool(scan.metadata.get("planner_enabled"))
        use_redteam = (
            scan.metadata.get("scan_mode") == "multi_agent_redteam"
            or (multi_agentic and planner_enabled)
        )
        probes = get_web_probes(owasp_filters, max_probes=self._config.webscan.max_probes_per_scan)
        if self._config.features.planner_v2:
            from agentarmor.orchestrator.planning.adapters import plan_web_probes_from_catalog

            web_plan = await plan_web_probes_from_catalog(self._config, probes)
            selected = set(web_plan.selected_ids)
            probes = [p for p in probes if p.id in selected] or probes
            scan.metadata["planner_audit"] = web_plan.audit_dict()
        scan.metadata["probe_count_planned"] = len(probes)
        scan.metadata["probe_count_executable"] = len(probes)

        auth_mode = scan.metadata.get("auth_mode", AuthMode.NONE.value)
        storage_state: dict | None = None
        if auth_mode == AuthMode.MANUAL_SESSION.value:
            storage_state = self._load_auth_storage(scan)
            if storage_state is None:
                scan.status = ScanStatus.FAILED
                scan.metadata["error"] = scan.metadata.get(
                    "auth_error", "authenticated session missing or expired"
                )
                scan.completed_at = datetime.now(timezone.utc)
                self._repo.save_scan(scan)
                await event_bus.publish_simple(
                    scan.id,
                    "scan.completed",
                    {"status": "failed", "error": scan.metadata["error"]},
                )
                return scan

        findings_count = 0
        evidence = EvidenceCollector(scan.id)

        try:
            async with self._pool.context(storage_state=storage_state) as ctx:
                page = await ctx.new_page()
                session = BrowserSession(
                    page,
                    allowlist=self._config.webscan.allowlist,
                    blocklist=self._config.webscan.blocklist,
                )
                await session.goto(
                    validated.normalized_url,
                    timeout_ms=int(self._config.webscan.timeout_s * 1000),
                )
                await event_bus.publish_simple(
                    scan.id,
                    "discovery.started",
                    {"page_url": validated.normalized_url},
                )
                discovery = await discover_full(
                    page,
                    validated.normalized_url,
                    session.network_log,
                    self._config,
                    use_llm_discovery=multi_agentic,
                )
                scan.metadata["discovery"] = discovery.model_dump(mode="json")
                if discovery.capability_map:
                    scan.metadata["capability_map"] = discovery.capability_map.model_dump(mode="json")
                if discovery.agent_risk:
                    scan.metadata["agent_risk"] = discovery.agent_risk.model_dump(mode="json")

                await event_bus.publish_simple(
                    scan.id,
                    "discovery.completed",
                    {
                        "widget_found": discovery.widget is not None,
                        "framework": discovery.framework,
                        "widget_confidence": discovery.widget.confidence if discovery.widget else None,
                        "candidate_count": len(discovery.candidates),
                        "low_confidence": bool(
                            discovery.widget
                            and discovery.widget.score_breakdown.get("low_confidence")
                        ),
                    },
                )

                if discovery.capability_map:
                    if planner_enabled and multi_agentic:
                        probes, attack_meta = await plan_web_attack_with_llm(
                            discovery.capability_map,
                            discovery.agent_risk,
                            scan_depth,
                            owasp_filters,
                            self._config.webscan.max_probes_per_scan,
                            self._config,
                            multi_agentic_max_probes=self._config.webscan.multi_agentic_max_probes,
                        )
                        scan.metadata["attack_plan"] = attack_meta
                    else:
                        probes = plan_web_attack(
                            discovery.capability_map,
                            discovery.agent_risk,
                            scan_depth,
                            owasp_filters,
                            self._config.webscan.max_probes_per_scan,
                            multi_agentic_max_probes=self._config.webscan.multi_agentic_max_probes,
                        )
                        scan.metadata["attack_plan"] = {"rule_probe_count": len(probes), "llm_probe_count": 0}
                    scan.metadata["probe_count_planned"] = len(probes)

                await event_bus.publish_simple(
                    scan.id,
                    "planning.completed",
                    {"probe_count": len(probes), "scan_mode": "multi_agent_redteam" if use_redteam else "standard"},
                )

                if not discovery.widget:
                    scan.status = ScanStatus.FAILED
                    scan.metadata["error"] = discovery.error or "no chat widget discovered"
                    scan.metadata["discovery_feedback"] = {
                        "candidate_count": len(discovery.candidates),
                        "heuristic_miss": True,
                        "framework": discovery.framework,
                    }
                    scan.completed_at = datetime.now(timezone.utc)
                    self._repo.save_scan(scan)
                    await event_bus.publish_simple(
                        scan.id,
                        "scan.completed",
                        {"status": "failed", "error": scan.metadata["error"]},
                    )
                    return scan

                widget = discovery.widget
                await event_bus.publish_simple(
                    scan.id,
                    "scan.started",
                    {
                        "probe_count": len(probes) if not use_redteam else self._config.redteam.multi_agent.max_rounds,
                        "scan_kind": "web",
                        "framework": discovery.framework,
                        "widget_confidence": widget.confidence,
                        "risk_score": discovery.agent_risk.risk_score if discovery.agent_risk else None,
                        "scan_mode": "multi_agent_redteam" if use_redteam else "standard",
                    },
                )

                if use_redteam:
                    from agentarmor.redteam.executor import WebExecutionContext
                    from agentarmor.redteam.orchestrator import RedTeamOrchestrator

                    scan.metadata["scan_mode"] = "multi_agent_redteam"
                    web_ctx = WebExecutionContext(
                        page=page,
                        widget=widget,
                        stable_ms=self._config.webscan.stable_ms,
                        max_wait_ms=self._config.webscan.max_wait_ms,
                    )
                    await RedTeamOrchestrator(self._config, self._repo).run(
                        scan,
                        web_ctx=web_ctx,
                        capability_map=discovery.capability_map,
                    )
                    findings_count = scan.finding_count
                    scan.status = ScanStatus.COMPLETED
                    scan.completed_at = datetime.now(timezone.utc)
                    self._repo.save_scan(scan)
                    await event_bus.publish_simple(
                        scan.id,
                        "scan.completed",
                        {
                            "status": "completed",
                            "finding_count": findings_count,
                            "scan_kind": "web",
                            "scan_mode": "multi_agent_redteam",
                        },
                    )
                    return scan

                for probe in probes:
                    await event_bus.publish_simple(
                        scan.id,
                        "probe.started",
                        {"probe_id": probe.id, "probe_name": probe.name},
                    )
                    t0 = time.perf_counter()
                    probe_error: str | None = None
                    response_text = ""
                    stable_meta: dict[str, Any] = {}
                    skip_reload = probe.turns >= 2 and probe.follow_up_prompt

                    try:
                        await event_bus.publish_simple(
                            scan.id,
                            "probe.waiting",
                            {"probe_id": probe.id, "probe_name": probe.name},
                        )
                        if skip_reload:
                            stable = await execute_multi_turn_probe(
                                page,
                                widget,
                                probe,
                                stable_ms=self._config.webscan.stable_ms,
                                max_wait_ms=self._config.webscan.max_wait_ms,
                            )
                        else:
                            stable = await execute_probe(
                                page,
                                widget,
                                probe,
                                stable_ms=self._config.webscan.stable_ms,
                                max_wait_ms=self._config.webscan.max_wait_ms,
                            )
                        response_text = stable.text
                        stable_meta = stable.model_dump()
                        await evidence.capture_probe(page, probe, stable, session.network_log)
                    except Exception as exc:
                        probe_error = str(exc)

                    latency_ms = (time.perf_counter() - t0) * 1000
                    probe_result = ProbeResult(
                        probe_id=probe.id,
                        probe_name=probe.name,
                        owasp=probe.owasp,
                        request=ProbeRequest(messages=[{"role": "user", "content": probe.prompt}]),
                        response=ProbeResponse(content=response_text, status_code=200 if not probe_error else 0),
                        latency_ms=latency_ms,
                        error=probe_error,
                        metadata={"webscan": True, "stable": stable_meta, "multi_turn": skip_reload},
                    )

                    if probe_error:
                        await event_bus.publish_simple(
                            scan.id,
                            "probe.completed",
                            {"probe_id": probe.id, "decision": "ERROR", "error": probe_error},
                        )
                        scan.probe_count += 1
                        continue

                    detection = await analyze_probe_result_async(
                        probe_result,
                        prompt_text=probe.prompt,
                        config=self._config.detection,
                    )
                    assertions = run_assertions(
                        probe_id=probe.id,
                        prompt=probe.prompt,
                        response=response_text,
                    )
                    assertion_score = composite_vuln_score(assertions)
                    if assertion_score >= self._config.detection.fail_threshold:
                        detection.decision = Decision.FAIL
                        detection.risk_score = max(detection.risk_score, assertion_score)
                        detection.severity = Severity.HIGH
                    elif assertion_score >= self._config.detection.warn_threshold:
                        if detection.decision == Decision.PASS:
                            detection.decision = Decision.WARN
                        detection.risk_score = max(detection.risk_score, assertion_score)

                    if multi_agentic:
                        judge = await judge_probe(
                            probe_id=probe.id,
                            probe_name=probe.name,
                            attack_prompt=probe.prompt,
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

                    if stable_meta.get("partial"):
                        if detection.decision == Decision.PASS:
                            detection.decision = Decision.WARN
                        detection.evidence.append("Stream did not complete before timeout")

                    risk_assessment = compute_risk_assessment(detection, reproducibility=0.5)

                    if detection.decision != Decision.PASS:
                        finding = Finding(
                            scan_id=scan.id,
                            probe_id=probe.id,
                            probe_name=probe.name,
                            owasp=probe.owasp,
                            title=f"{probe.name} — {detection.severity.value}",
                            description=f"Web probe {probe.id} detected a potential security issue.",
                            severity=detection.severity,
                            decision=detection.decision,
                            risk_score=risk_assessment.risk_score / 100.0,
                            evidence=detection.evidence,
                            request_summary=probe.prompt[:500],
                            response_excerpt=response_text[:1000],
                            risk_assessment=risk_assessment,
                            metadata={
                                "detection_layers": detection.layers,
                                "scan_kind": "web",
                                "framework": discovery.framework,
                                "stream_metadata": stable_meta,
                                "capability_map": scan.metadata.get("capability_map"),
                            },
                        )
                        enrichment = await enrich_finding(finding, probe_result, self._config)
                        finding.metadata["enrichment"] = enrichment.model_dump()
                        self._repo.save_finding(finding)
                        findings_count += 1

                    scan.probe_count += 1
                    await event_bus.publish_simple(
                        scan.id,
                        "probe.completed",
                        {
                            "probe_id": probe.id,
                            "decision": detection.decision.value,
                            "risk_score": detection.risk_score,
                        },
                    )

                    if not skip_reload:
                        try:
                            await session.goto(
                                validated.normalized_url,
                                timeout_ms=int(self._config.webscan.timeout_s * 1000),
                            )
                        except Exception:
                            pass

        finally:
            await self._pool.close()

        findings = self._repo.list_findings(scan_id=scan.id)
        if self._config.features.finding_groups and findings:
            clustered = cluster_findings(findings, self._config)
            for finding in clustered:
                self._repo.merge_finding(finding)
            findings_count = len(
                [f for f in clustered if f.metadata.get("is_cluster_primary", True)]
            )
            scan.metadata["finding_count_raw"] = len(clustered)
        else:
            findings_count = len(findings)

        scan.finding_count = findings_count
        scan.status = ScanStatus.COMPLETED
        scan.completed_at = datetime.now(timezone.utc)
        self._repo.save_scan(scan)
        await event_bus.publish_simple(
            scan.id,
            "scan.completed",
            {"status": "completed", "finding_count": findings_count, "scan_kind": "web"},
        )
        return scan


def build_web_scan(
    page_url: str,
    *,
    owasp_filters: list[str] | None = None,
    scan_depth: ScanDepth = ScanDepth.STANDARD,
    auth_mode: AuthMode = AuthMode.NONE,
    planner_enabled: bool = False,
) -> Scan:
    return Scan(
        target=Target(type=TargetType.ENDPOINT, url=page_url),
        metadata={
            "scan_kind": "web",
            "page_url": page_url,
            "owasp_filters": owasp_filters or ["LLM01", "LLM02", "LLM05", "LLM06", "LLM07", "LLM08", "LLM09"],
            "scan_depth": scan_depth.value,
            "auth_mode": auth_mode.value,
            "planner_enabled": planner_enabled,
        },
    )
