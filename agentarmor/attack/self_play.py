"""Self-play red teaming — Attacker vs Target vs Defender vs Judge loop."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from agentarmor.attack.goals import get_goal
from agentarmor.attack.models import L0Variant
from agentarmor.attack.mutations.registry import MUTATION_REGISTRY, apply_mutation, list_mutations
from agentarmor.attack.risk import compute_risk_assessment
from agentarmor.core.config import AppConfig
from agentarmor.core.models import (
    AttackStep,
    AttackTree,
    Decision,
    Finding,
    ProbeRequest,
    ProbeResult,
    ProbeResponse,
    Severity,
)
from agentarmor.detection.agentic.judge import apply_judge_to_detection, judge_probe
from agentarmor.detection.agentic.prompts import ATTACKER_SYSTEM, DEFENDER_SYSTEM
from agentarmor.detection.pipeline import analyze_probe_result_async
from agentarmor.engines.router import send_probe


class SelfPlayRound(BaseModel):
    round_num: int
    probe_id: str
    technique: str
    attack_prompt: str
    response_excerpt: str = ""
    judge_vulnerable: bool = False
    judge_confidence: float = 0.0
    defender_blocked: bool | None = None


class SelfPlayResult(BaseModel):
    attack_goal: str
    successful: bool = False
    rounds: list[SelfPlayRound] = Field(default_factory=list)
    attack_tree: AttackTree | None = None
    findings: list[Finding] = Field(default_factory=list)


@dataclass
class _AttackCandidate:
    prompt: str
    technique: str
    probe_id: str
    mutated_from: str | None = None


async def run_self_play_for_goal(
    config: AppConfig,
    *,
    scan_id: str,
    goal_id: str,
) -> SelfPlayResult:
    """Run self-play loop for a single attack goal."""
    sp_cfg = config.detection.self_play
    goal = get_goal(goal_id)
    if goal is None:
        return SelfPlayResult(attack_goal=goal_id)

    seed = goal.seeds[0] if goal.seeds else f"Test goal: {goal.name}"
    candidates = _offline_candidates(goal_id, goal.name, seed, sp_cfg.max_rounds)
    result = SelfPlayResult(attack_goal=goal_id)
    path_steps: list[AttackStep] = []
    prior_attempts: list[str] = []

    for round_num, candidate in enumerate(candidates[: sp_cfg.max_rounds], start=1):
        probe_result = await send_probe(
            config,
            candidate.probe_id,
            f"Self-play — {goal.name}",
            goal.owasp,
            ProbeRequest(
                messages=[{"role": "user", "content": candidate.prompt}],
                model=config.target.model or "gpt-3.5-turbo",
            ),
        )
        response_text = probe_result.response.content or ""
        prior_attempts.append(candidate.prompt[:200])

        defender_blocked = None
        if sp_cfg.defender_enabled and config.detection.analysis_mode == "cloud":
            defender_blocked = await _run_defender(candidate.prompt, config)

        detection = await analyze_probe_result_async(
            probe_result,
            prompt_text=candidate.prompt,
            config=config.detection,
        )

        judge = await judge_probe(
            probe_id=candidate.probe_id,
            probe_name=f"Self-play {goal.name}",
            attack_prompt=candidate.prompt,
            response=response_text,
            config=config,
        )
        if judge:
            risk, decision, sev = apply_judge_to_detection(
                detection.risk_score, detection.decision, judge
            )
            detection.risk_score = risk
            detection.decision = decision
            if sev and decision != Decision.PASS:
                detection.severity = sev

        round_record = SelfPlayRound(
            round_num=round_num,
            probe_id=candidate.probe_id,
            technique=candidate.technique,
            attack_prompt=candidate.prompt[:500],
            response_excerpt=response_text[:300],
            judge_vulnerable=bool(judge and judge.vulnerable),
            judge_confidence=float(judge.confidence if judge else 0.0),
            defender_blocked=defender_blocked,
        )
        result.rounds.append(round_record)

        path_steps.append(
            AttackStep(
                step=candidate.technique,
                probe_id=candidate.probe_id,
                mutated_from=candidate.mutated_from,
                evidence=(judge.rationale[:200] if judge and judge.rationale else None),
            )
        )

        success = detection.decision != Decision.PASS or (judge is not None and judge.vulnerable)
        if success:
            result.successful = True
            risk_assessment = compute_risk_assessment(detection, reproducibility=1.0)
            finding = Finding(
                scan_id=scan_id,
                probe_id=candidate.probe_id,
                probe_name=f"Self-play — {goal.name} ({candidate.technique})",
                owasp=goal.owasp,
                title=f"Self-play discovered — {detection.severity.value}",
                description=f"Self-play round {round_num} confirmed vulnerability for {goal_id}.",
                severity=detection.severity,
                decision=detection.decision,
                risk_score=risk_assessment.risk_score / 100.0,
                evidence=detection.evidence,
                request_summary=candidate.prompt[:500],
                response_excerpt=response_text[:1000],
                risk_assessment=risk_assessment,
                metadata={
                    "attack_goal": goal_id,
                    "self_play": True,
                    "round": round_num,
                    "technique": candidate.technique,
                    "mutation_chain": [candidate.technique],
                    "risk_assessment": risk_assessment.model_dump(),
                },
            )
            result.findings.append(finding)
            if sp_cfg.stop_on_success:
                break

        # Cloud attacker generates next candidate when budget remains
        if (
            not success
            and round_num < sp_cfg.max_rounds
            and config.detection.analysis_mode == "cloud"
            and config.detection.agentic.enabled
            and config.detection.agentic.api_key
        ):
            next_attack = await _cloud_attacker(
                goal_id=goal_id,
                goal_name=goal.name,
                prior_attempts=prior_attempts,
                last_response=response_text,
                config=config,
            )
            if next_attack:
                candidates.insert(
                    round_num,
                    _AttackCandidate(
                        prompt=next_attack["prompt"],
                        technique=next_attack.get("technique", "cloud_attacker"),
                        probe_id=f"selfplay.{goal_id}.cloud.{round_num + 1}",
                        mutated_from=candidate.probe_id,
                    ),
                )

    result.attack_tree = AttackTree(
        attack_goal=goal_id,
        path=path_steps,
        successful=result.successful,
    )
    return result


async def run_self_play_scan(config: AppConfig, scan_id: str) -> SelfPlayResult:
    """Run self-play for all configured goals; merge into one aggregate result."""
    sp_cfg = config.detection.self_play
    merged = SelfPlayResult(attack_goal="self_play")
    for goal_id in sp_cfg.goals:
        partial = await run_self_play_for_goal(config, scan_id=scan_id, goal_id=goal_id)
        merged.rounds.extend(partial.rounds)
        merged.findings.extend(partial.findings)
        if partial.successful:
            merged.successful = True
            if partial.attack_tree:
                merged.attack_tree = partial.attack_tree
    return merged


def _offline_candidates(
    goal_id: str,
    goal_name: str,
    seed: str,
    max_rounds: int,
) -> list[_AttackCandidate]:
    """Deterministic mutation chain for offline self-play."""
    candidates: list[_AttackCandidate] = [
        _AttackCandidate(
            prompt=seed,
            technique="seed",
            probe_id=f"selfplay.{goal_id}.seed",
        )
    ]
    seen = {seed}
    for mut_name in list_mutations():
        if len(candidates) >= max_rounds:
            break
        mutated = apply_mutation(mut_name, seed)
        if mutated in seen:
            continue
        seen.add(mutated)
        label = MUTATION_REGISTRY.get(mut_name, (mut_name,))[0]
        candidates.append(
            _AttackCandidate(
                prompt=mutated,
                technique=label,
                probe_id=f"selfplay.{goal_id}.{mut_name}",
                mutated_from=f"selfplay.{goal_id}.seed",
            )
        )
    return candidates


async def _cloud_attacker(
    *,
    goal_id: str,
    goal_name: str,
    prior_attempts: list[str],
    last_response: str,
    config: AppConfig,
) -> dict | None:
    agentic = config.detection.agentic
    user = (
        f"attack_goal: {goal_name} ({goal_id})\n"
        f"prior_attempts: {json.dumps(prior_attempts[-5:])}\n"
        f"last_response: {last_response[:1500]}\n"
        "Generate the next attack prompt."
    )
    import litellm

    try:
        model = agentic.model
        if "/" not in model:
            model = f"{agentic.provider}/{model}"
        completion = await litellm.acompletion(
            model=model,
            api_key=agentic.api_key or None,
            messages=[
                {"role": "system", "content": ATTACKER_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            max_tokens=600,
        )
        content = (completion.choices[0].message.content or "").strip()
        return _parse_json_object(content)
    except Exception:
        return None


async def _run_defender(prompt: str, config: AppConfig) -> bool | None:
    agentic = config.detection.agentic
    import litellm

    try:
        model = agentic.model
        if "/" not in model:
            model = f"{agentic.provider}/{model}"
        completion = await litellm.acompletion(
            model=model,
            api_key=agentic.api_key or None,
            messages=[
                {"role": "system", "content": DEFENDER_SYSTEM},
                {"role": "user", "content": f"attack_prompt: {prompt[:1500]}"},
            ],
            temperature=0.0,
            max_tokens=300,
        )
        content = (completion.choices[0].message.content or "").strip()
        parsed = _parse_json_object(content)
        if parsed:
            return bool(parsed.get("blocked"))
    except Exception:
        return None
    return None


def _parse_json_object(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
