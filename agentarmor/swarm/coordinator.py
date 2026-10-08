"""Run a swarm: many members, one goal, bounded concurrency, shared discoveries.

The load-bearing decision here is that **member coroutines are pure**. Each one
returns a ``MemberOutcome`` and mutates nothing shared except the explicitly
locked blackboard. Everything else - the trace, the solved-node set, findings,
counters - is written only by the coordinator coroutine as it drains results. That
keeps ``SwarmTrace`` single-writer with no locking, which matters because the
red-team trace it mirrors was built for a strictly sequential loop.

Members run in a **worker pool** sized to ``max_concurrent``, not in waves. A
wave barrier would hold agent 7's secret back from agents 8 to 16 until the slowest
member of the wave finished, which defeats the point of the blackboard. The pool
starts the next member the moment one finishes, so a member that starts late takes
a brief containing everything completed before it.

The pool is also why the coordinator, rather than each member, decides when a
member starts. An earlier version launched every member behind a semaphore and had
members check the solved-node set themselves; that raced, because fast members
outran the coordinator's bookkeeping and the check almost never fired. Deciding at
launch is deterministic and leaves member coroutines touching no shared mutable
state at all.

Two more things the sequential loop did that do not survive at this scale:

- It saved the whole scan every round, re-serialising a growing trace. At 100
  members that is quadratic in bytes and serialised by SQLite, so persistence is
  debounced here.
- It enriched every finding. Enrichment is a five-agent pipeline, so it is capped
  by count *and* metered against the same budget ceiling.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentarmor.attack.risk import compute_risk_assessment
from agentarmor.core.config import AppConfig
from agentarmor.core.events import event_bus
from agentarmor.core.models import Decision, Finding, ProbeResult, Scan, ScanStatus, Severity
from agentarmor.db.session import ScanRepository
from agentarmor.detection.assertions import composite_vuln_score, run_assertions
from agentarmor.detection.judge_service import apply_verdict_to_detection, judge_probe_verdict
from agentarmor.detection.pipeline import analyze_probe_result_async
from agentarmor.redteam.agents.attack.generator import judge_rubric_for_node
from agentarmor.redteam.executor import WebExecutionContext, execute_attack
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.graph.profile import (
    profile_from_capability_map,
    profile_from_config,
    profile_from_metadata,
)
from agentarmor.redteam.schemas import TargetProfile
from agentarmor.redteam.verdict import build_verdict
from agentarmor.reporting.enrichment import enrich_finding
from agentarmor.swarm import events as swarm_events
from agentarmor.swarm.blackboard import Blackboard
from agentarmor.swarm.budget import AsyncBudgetGovernor, MemberMeter
from agentarmor.swarm.facts import extract_facts
from agentarmor.swarm.goals import get_swarm_goal, list_swarm_goal_ids
from agentarmor.swarm.lead import LeadAgent
from agentarmor.swarm.member import SwarmMemberAgent, plan_for
from agentarmor.swarm.roster import build_roster, compute_coverage
from agentarmor.swarm.schemas import (
    Fact,
    MemberRecord,
    SwarmGoal,
    SwarmMember,
    SwarmSummary,
    SwarmTrace,
)


@dataclass
class MemberOutcome:
    """What one member coroutine returns. Nothing in here is shared state."""

    member: SwarmMember
    record: MemberRecord
    new_facts: list[Fact] = field(default_factory=list)
    finding: Finding | None = None
    result: ProbeResult | None = None
    skipped: bool = False


class SwarmCoordinator:
    def __init__(self, config: AppConfig, repo: ScanRepository) -> None:
        self._config = config
        self._repo = repo
        self._last_persist = 0.0
        self._last_progress = 0.0

    # -- preflight ----------------------------------------------------------

    def _require_cloud_key(self) -> None:
        detection = self._config.detection
        if detection.analysis_mode != "cloud" or not detection.agentic.api_key:
            raise ValueError(
                "An analysis API key is required. AgentArmor runs multi-agent "
                "analysis on every scan - set AGENTARMOR_ANALYSIS_API_KEY in the "
                "environment, configure it in Settings, or pass --analysis-api-key."
            )

    def _profile_for(self, scan: Scan, capability_map: Any | None) -> TargetProfile:
        if capability_map is not None:
            return profile_from_capability_map(capability_map)
        metadata = scan.metadata or {}
        if metadata.get("capabilities"):
            return profile_from_metadata(metadata)
        return profile_from_config(self._config, None)

    # -- persistence --------------------------------------------------------

    def _persist(self, scan: Scan, *, force: bool = False) -> None:
        now = time.monotonic()
        interval = self._config.swarm.persist_interval_s
        if not force and (now - self._last_persist) < interval:
            return
        self._last_persist = now
        self._repo.save_scan(scan)

    # -- one member ---------------------------------------------------------

    async def _run_member(
        self,
        *,
        member: SwarmMember,
        scan: Scan,
        profile: TargetProfile,
        board: Blackboard,
        governor: AsyncBudgetGovernor,
        wave: int,
        web_ctx: WebExecutionContext | None,
    ) -> MemberOutcome:
        cfg = self._config
        meter = MemberMeter(member.member_id, governor)
        record = MemberRecord(
            member_id=member.member_id,
            node_id=member.node_id,
            path_id=member.path_id,
            persona_id=member.persona_id,
            skill_id=member.skill_id,
            strategy=member.strategy,
            wave=wave,
        )

        reservation = await governor.try_reserve()
        if reservation is None:
            record.error = "skipped: budget exhausted"
            record.skipped = True
            return MemberOutcome(member=member, record=record, skipped=True)

        started = time.perf_counter()
        await event_bus.publish_simple(
            scan.id,
            swarm_events.AGENT_STARTED,
            {
                "member_id": member.member_id,
                "node_id": member.node_id,
                "path_id": member.path_id,
                "persona_id": member.persona_id,
                "wave": wave,
            },
        )
        try:
            agent = SwarmMemberAgent(member, board)
            plan = plan_for(member)
            attack = await agent.generate(cfg, meter, profile, plan)
            result, prompt_text, conversation = await execute_attack(
                cfg, attack, web_ctx=web_ctx
            )
            response_text = result.response.content or ""

            detection = await analyze_probe_result_async(
                result, prompt_text=prompt_text, config=cfg.detection
            )
            detection = self._apply_assertions(
                attack.probe_id, prompt_text, response_text, detection
            )

            rubric = agent.judge_rubric_for(member.node_id) or judge_rubric_for_node(
                member.node_id
            )
            judge = await judge_probe_verdict(
                probe_id=attack.probe_id,
                probe_name=attack.name,
                attack_prompt=prompt_text,
                response=response_text,
                config=cfg,
                rubric=rubric or None,
                meter=meter,
            )
            if judge:
                detection = self._apply_judge(
                    attack.probe_id, prompt_text, response_text, detection, judge
                )

            verdict = build_verdict(
                plan=plan,
                attack=attack,
                detection=detection,
                judge=judge,
                path_outcomes={member.node_id: []},
            )

            facts = extract_facts(
                config=cfg,
                member_id=member.member_id,
                node_id=member.node_id,
                owasp=list(attack.owasp or member.owasp),
                response_text=response_text,
                detection=detection,
                judge_quotes=list(judge.evidence_quotes) if judge else None,
                judge_confidence=judge.confidence if judge else 0.0,
                profile_tools=list(profile.tools),
                wave=wave,
            )
            # Published from the member, not the coordinator: with a semaphore
            # members start staggered, so a member acquiring the semaphore later
            # should already see what finished before it.
            new_facts = await board.publish(facts)

            finding: Finding | None = None
            if verdict.vulnerable:
                risk_assessment = compute_risk_assessment(
                    detection, reproducibility=verdict.reproducibility_score
                )
                finding = Finding(
                    scan_id=scan.id,
                    probe_id=attack.probe_id,
                    probe_name=attack.name,
                    owasp=attack.owasp,
                    title=f"Swarm - {attack.name} ({verdict.impact_score})",
                    description=verdict.rationale
                    or f"Swarm member {member.member_id} succeeded on {member.node_id}.",
                    severity=detection.severity,
                    decision=detection.decision,
                    risk_score=risk_assessment.risk_score / 100.0,
                    evidence=detection.evidence + verdict.evidence_quotes,
                    request_summary=prompt_text[:500],
                    response_excerpt=response_text[:1000],
                    risk_assessment=risk_assessment,
                    metadata={
                        "scan_mode": "swarm",
                        "member_id": member.member_id,
                        "attack_path": member.path_id,
                        "node_id": member.node_id,
                        "persona_id": member.persona_id,
                        "strategy": member.strategy,
                        "subgoal": member.subgoal,
                        "wave": wave,
                        "redteam_verdict": verdict.model_dump(),
                        "conversation": conversation,
                    },
                )

            record.vulnerable = verdict.vulnerable
            record.decision = detection.decision.value
            record.confidence = verdict.confidence_score
            record.facts_published = len(new_facts)
            record.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            record.tokens = meter.tokens
            record.cost_usd = meter.cost_usd
            record.calls = meter.calls
            return MemberOutcome(
                member=member,
                record=record,
                new_facts=new_facts,
                finding=finding,
                result=result,
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - one member must not abort the swarm
            record.error = str(exc)
            record.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            record.tokens = meter.tokens
            record.cost_usd = meter.cost_usd
            record.calls = meter.calls
            return MemberOutcome(member=member, record=record)
        finally:
            await governor.settle(reservation)

    def _apply_assertions(self, probe_id, prompt_text, response_text, detection):
        from agentarmor.detection.probe_thresholds import resolve_probe_thresholds

        cfg = self._config
        l1_score = float(detection.layers.get("l1", {}).get("score", 0))
        l4_outcomes = float(
            (detection.layers.get("l4", {}) or {}).get("components", {}).get("outcomes", 0)
        )
        thresholds = resolve_probe_thresholds(probe_id, cfg.detection)
        assertions = run_assertions(
            probe_id=probe_id,
            prompt=prompt_text,
            response=response_text,
            tiered_compliance=cfg.detection.experimental.tiered_compliance,
            l1_score=l1_score,
            l4_outcome_score=l4_outcomes,
            refusal_escalation=thresholds.refusal_escalation,
        )
        score = composite_vuln_score(assertions)
        if score >= thresholds.fail_threshold:
            detection.decision = Decision.FAIL
            detection.risk_score = max(detection.risk_score, score)
            detection.severity = Severity.HIGH
        elif score >= thresholds.warn_threshold:
            if detection.decision == Decision.PASS:
                detection.decision = Decision.WARN
            detection.risk_score = max(detection.risk_score, score)
        return detection

    def _apply_judge(self, probe_id, prompt_text, response_text, detection, judge):
        from agentarmor.detection.probe_thresholds import resolve_probe_thresholds

        cfg = self._config
        thresholds = resolve_probe_thresholds(probe_id, cfg.detection)
        l1_score = float(detection.layers.get("l1", {}).get("score", 0))
        risk, decision, severity_override = apply_verdict_to_detection(
            detection.risk_score,
            detection.decision,
            judge,
            fail_threshold=thresholds.fail_threshold,
            warn_threshold=thresholds.warn_threshold,
            probe_id=probe_id,
            prompt=prompt_text,
            response=response_text,
            detection=cfg.detection,
            l1_score=l1_score,
        )
        detection.risk_score = risk
        detection.decision = decision
        if severity_override and decision != Decision.PASS:
            detection.severity = severity_override
        return detection

    # -- the run ------------------------------------------------------------

    async def run(
        self,
        scan: Scan,
        *,
        web_ctx: WebExecutionContext | None = None,
        capability_map: Any | None = None,
    ) -> Scan:
        self._require_cloud_key()
        cfg = self._config

        goal_id = str((scan.metadata or {}).get("goal_id") or "")
        goal: SwarmGoal | None = get_swarm_goal(goal_id)
        if goal is None:
            raise ValueError(
                f"Unknown swarm goal '{goal_id}'. "
                f"Choose one of: {', '.join(list_swarm_goal_ids())}"
            )

        requested = int((scan.metadata or {}).get("agent_count") or cfg.swarm.default_agents)
        max_concurrent = int(
            (scan.metadata or {}).get("max_concurrent") or cfg.swarm.default_concurrent
        )
        profile = self._profile_for(scan, capability_map)
        paths = build_attack_graph(profile)

        governor = AsyncBudgetGovernor(cfg.swarm.budget)
        board = Blackboard(
            max_facts=cfg.swarm.blackboard.max_facts,
            max_fact_chars=cfg.swarm.blackboard.max_fact_chars,
            brief_max_chars=cfg.swarm.blackboard.brief_max_chars,
        )

        lead = LeadAgent(goal, profile, paths)
        plan = await lead.plan(cfg, governor)
        roster = lead.assign(plan, build_roster(goal, profile, paths, size=requested))
        coverage = compute_coverage(roster, concurrency=max_concurrent)

        trace = SwarmTrace(
            goal_id=goal.id,
            agents_requested=requested,
            agents=len(roster),
            max_concurrent=max_concurrent,
            coverage=coverage,
            roster=list(roster),
        )
        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        scan.metadata["scan_kind"] = "swarm"
        scan.metadata["swarm_trace"] = trace.model_dump(mode="json")
        self._persist(scan, force=True)

        await event_bus.publish_simple(
            scan.id,
            "scan.started",
            {
                "probe_count": len(roster),
                "scan_kind": "swarm",
                "goal_id": goal.id,
                "coverage": coverage.model_dump(),
            },
        )
        await event_bus.publish_simple(
            scan.id,
            swarm_events.SWARM_PLAN,
            {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "llm_planned": plan.llm_planned,
                "subgoals": len(plan.subgoals),
                "coverage": coverage.model_dump(),
            },
        )
        # One batched event, not one per member: a hundred spawn events would be
        # pure noise on a stream the GUI already has to keep up with.
        await event_bus.publish_simple(
            scan.id,
            swarm_events.SWARM_ROSTER,
            {"members": [m.model_dump(mode="json") for m in roster]},
        )

        solved: set[str] = set()
        findings: list[Finding] = []
        cancelled = False
        enriched = 0
        launched = 0

        # A worker pool rather than "launch everything behind a semaphore". The
        # pool size *is* the concurrency cap, and because the coordinator decides
        # when each member starts it can consult `solved` itself. With a semaphore
        # that check had to live inside the member coroutine, where it raced: fast
        # members outran the coordinator's bookkeeping and the skip almost never
        # fired. Deciding at launch is deterministic, and no member touches shared
        # mutable state at all.
        pending: list[tuple[int, SwarmMember]] = list(enumerate(roster))
        pending.reverse()  # pop() from the end, preserving roster order
        running: set[asyncio.Task[MemberOutcome]] = set()
        skipped_records: list[MemberRecord] = []

        def launch_available() -> None:
            nonlocal launched
            while pending and len(running) < max(1, max_concurrent):
                position, member = pending.pop()
                if member.node_id in solved and cfg.redteam.multi_agent.stop_on_vulnerability:
                    # Another member already broke this node. Retire the rest of
                    # the queue for it rather than spending budget to re-prove it.
                    record = MemberRecord(
                        member_id=member.member_id,
                        node_id=member.node_id,
                        path_id=member.path_id,
                        persona_id=member.persona_id,
                        skill_id=member.skill_id,
                        strategy=member.strategy,
                        wave=position // max(1, max_concurrent),
                        skipped=True,
                        error="skipped: node already solved",
                    )
                    skipped_records.append(record)
                    continue
                launched += 1
                running.add(
                    asyncio.create_task(
                        self._run_member(
                            member=member,
                            scan=scan,
                            profile=profile,
                            board=board,
                            governor=governor,
                            wave=position // max(1, max_concurrent),
                            web_ctx=web_ctx,
                        )
                    )
                )


        async def drain_skipped() -> None:
            while skipped_records:
                record = skipped_records.pop(0)
                trace.members.append(record)
                await event_bus.publish_simple(
                    scan.id,
                    swarm_events.AGENT_SKIPPED,
                    {"member_id": record.member_id, "reason": record.error or "skipped"},
                )

        try:
            launch_available()
            await drain_skipped()
            while running:
                done, running = await asyncio.wait(
                    running, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    outcome = task.result()
                    # ---- single-writer region: coordinator coroutine only ----
                    trace.members.append(outcome.record)
                    trace.node_outcomes.setdefault(outcome.member.node_id, []).append(
                        outcome.record.vulnerable
                    )
                    if outcome.record.vulnerable:
                        solved.add(outcome.member.node_id)

                    if outcome.skipped:
                        await event_bus.publish_simple(
                            scan.id,
                            swarm_events.AGENT_SKIPPED,
                            {
                                "member_id": outcome.record.member_id,
                                "reason": outcome.record.error or "skipped",
                            },
                        )
                    elif outcome.record.error:
                        await event_bus.publish_simple(
                            scan.id,
                            swarm_events.AGENT_FAILED,
                            {
                                "member_id": outcome.record.member_id,
                                "error": outcome.record.error,
                            },
                        )
                    else:
                        scan.probe_count += 1
                        await event_bus.publish_simple(
                            scan.id,
                            swarm_events.AGENT_COMPLETED,
                            outcome.record.model_dump(mode="json"),
                        )

                    for fact in outcome.new_facts:
                        await event_bus.publish_simple(
                            scan.id,
                            swarm_events.BLACKBOARD_FACT,
                            fact.model_dump(mode="json"),
                        )

                    if outcome.finding is not None:
                        finding = outcome.finding
                        if enriched < cfg.swarm.max_findings_per_swarm:
                            enriched += 1
                            enrichment = await enrich_finding(
                                finding,
                                outcome.result,  # type: ignore[arg-type]
                                cfg,
                                meter=_EnrichmentMeter(governor),
                            )
                            finding.metadata["enrichment"] = enrichment.model_dump()
                            if enrichment.plain_title:
                                finding.title = enrichment.plain_title
                        findings.append(finding)
                        self._repo.save_finding(finding)

                trace.budget = governor.state
                scan.metadata["swarm_trace"] = trace.model_dump(mode="json")
                self._persist(scan)
                await self._publish_progress(scan, trace, governor, len(findings), len(roster))
                launch_available()
                await drain_skipped()

        except asyncio.CancelledError:
            cancelled = True
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
        finally:
            for task in running:
                if not task.done():
                    task.cancel()

        summary = self._build_summary(
            goal=goal,
            trace=trace,
            governor=governor,
            board_size=await board.size(),
            findings=len(findings),
            cancelled=cancelled,
        )
        scan.finding_count = len(findings)
        scan.completed_at = datetime.now(timezone.utc)
        scan.status = ScanStatus.CANCELLED if cancelled else ScanStatus.COMPLETED
        trace.budget = governor.state
        scan.metadata["swarm_trace"] = trace.model_dump(mode="json")
        scan.metadata["swarm_blackboard"] = await board.snapshot()
        scan.metadata["swarm_summary"] = summary.model_dump(mode="json")
        self._persist(scan, force=True)

        await event_bus.publish_simple(
            scan.id, swarm_events.SWARM_COMPLETED, summary.model_dump(mode="json")
        )
        # Terminator. Without it the SSE generator never breaks and the GUI hangs.
        await event_bus.publish_simple(
            scan.id,
            "scan.completed",
            {
                "status": scan.status.value,
                "finding_count": len(findings),
                "scan_kind": "swarm",
            },
        )
        if cancelled:
            raise asyncio.CancelledError()
        return scan

    async def _publish_progress(self, scan, trace, governor, findings, total) -> None:
        now = time.monotonic()
        if (now - self._last_progress) < swarm_events.PROGRESS_INTERVAL_S:
            return
        self._last_progress = now
        await event_bus.publish_simple(
            scan.id,
            swarm_events.SWARM_PROGRESS,
            {
                "completed": len(trace.members),
                "total": total,
                "findings": findings,
                "tokens_used": governor.state.tokens_used,
                "member_cost_usd": governor.member_cost_usd,
                "enrichment_cost_usd": governor.enrichment_cost_usd,
                "total_cost_usd": governor.total_cost_usd,
                "degraded": governor.degraded,
            },
        )

    def _build_summary(
        self, *, goal, trace, governor, board_size, findings, cancelled
    ) -> SwarmSummary:
        completed = [r for r in trace.members if not r.error]
        skipped = [r for r in trace.members if r.skipped]
        # Only genuine errors. Conflating skips with failures makes a healthy run -
        # one where the first wave solved every node - read as mostly broken.
        failed = [r for r in trace.members if r.error and not r.skipped]
        return SwarmSummary(
            goal_id=goal.id,
            goal_name=goal.name,
            agents_requested=trace.agents_requested,
            agents=trace.agents,
            max_concurrent=trace.max_concurrent,
            completed=len(completed),
            skipped=len(skipped),
            failed=len(failed),
            vulnerable=len([r for r in trace.members if r.vulnerable]),
            findings=findings,
            waves=max((r.wave for r in trace.members), default=0) + 1,
            blackboard_facts=board_size,
            member_cost_usd=governor.member_cost_usd,
            enrichment_cost_usd=governor.enrichment_cost_usd,
            total_cost_usd=governor.total_cost_usd,
            tokens_used=governor.state.tokens_used,
            degraded=governor.degraded,
            stopped=governor.state.stopped,
            stop_reason=governor.state.stop_reason or "",
            cancelled=cancelled,
            coverage=trace.coverage,
        )


@dataclass
class _EnrichmentMeter:
    """Routes enrichment spend to the governor's enrichment stream."""

    governor: AsyncBudgetGovernor

    def record_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        litellm_cost: float | None = None,
    ) -> None:
        self.governor.record_enrichment_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            litellm_cost=litellm_cost,
        )
