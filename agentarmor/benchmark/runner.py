"""Benchmark runner — multi-target probe execution."""

from __future__ import annotations

from datetime import datetime, timezone

from agentarmor.benchmark.models import (
    BenchmarkRun,
    BenchmarkStatus,
    ProbeBenchmarkResult,
)
from agentarmor.benchmark.scorer import decision_penalty, rank_models, score_model
from agentarmor.benchmark.suite_loader import BenchmarkSuite, ResolvedProbe, load_suite, resolve_suite_probes
from agentarmor.benchmark.models import BenchmarkTarget
from agentarmor.core.config import AppConfig
from agentarmor.core.models import Decision, ProbeRequest, Target, TargetType
from agentarmor.detection.pipeline import analyze_probe_result
from agentarmor.engines.router import send_probe


def _config_for_target(base: AppConfig, target: BenchmarkTarget) -> AppConfig:
    cfg = base.model_copy(deep=True)
    if target.type == "provider":
        cfg.target = Target(
            type=TargetType.PROVIDER,
            provider=target.provider,
            model=target.model or "gpt-3.5-turbo",
        )
    elif target.type == "local":
        cfg.target = Target(type=TargetType.LOCAL, model=target.model)
    else:
        raise ValueError(f"Unsupported benchmark target type: {target.type}")
    return cfg


async def _run_probe(
    config: AppConfig,
    resolved: ResolvedProbe,
    suite: BenchmarkSuite,
) -> ProbeBenchmarkResult:
    if resolved.multi_turn is not None:
        steps = resolved.multi_turn.get_conversation_steps(config)
        model = config.target.model or "gpt-3.5-turbo"
        last_content = ""
        for turn_messages in steps:
            request = ProbeRequest(messages=turn_messages, model=model)
            result = await send_probe(
                config,
                resolved.probe_id,
                resolved.multi_turn.name,
                resolved.multi_turn.owasp,
                request,
            )
            last_content = result.response.content or ""
        prompt_text = steps[-1][-1]["content"] if steps[-1] else ""
        from agentarmor.core.models import ProbeResponse, ProbeResult

        result = ProbeResult(
            probe_id=resolved.probe_id,
            probe_name=resolved.multi_turn.name,
            owasp=resolved.multi_turn.owasp,
            request=ProbeRequest(messages=steps[-1] if steps else []),
            response=ProbeResponse(content=last_content),
        )
    else:
        assert resolved.definition is not None
        request = resolved.definition.build_request(config)
        prompt_text = request.messages[0]["content"] if request.messages else ""
        result = await send_probe(
            config,
            resolved.probe_id,
            resolved.definition.name,
            resolved.definition.owasp,
            request,
        )

    detection = analyze_probe_result(result, prompt_text=prompt_text, config=config.detection)
    risk = decision_penalty(detection.decision, detection.risk_score, suite)
    return ProbeBenchmarkResult(
        probe_id=resolved.probe_id,
        category_id=resolved.category_id,
        decision=detection.decision.value,
        risk_score=risk,
        severity=detection.severity.value,
    )


async def run_benchmark(
    base_config: AppConfig,
    suite_name: str,
    targets: list[BenchmarkTarget],
) -> BenchmarkRun:
    suite = load_suite(suite_name)
    probes = resolve_suite_probes(suite)
    run = BenchmarkRun(
        suite_id=suite.id,
        suite_name=suite.name,
        status=BenchmarkStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        metadata={"suite_version": suite.version, "target_count": len(targets)},
    )

    model_scores = []
    for target in targets:
        cfg = _config_for_target(base_config, target)
        results: list[ProbeBenchmarkResult] = []
        for resolved in probes:
            results.append(await _run_probe(cfg, resolved, suite))
        model_scores.append(
            score_model(
                suite,
                target.label,
                target.type,
                target.provider,
                target.model,
                results,
            )
        )

    run.model_scores = rank_models(model_scores)
    run.status = BenchmarkStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    return run
