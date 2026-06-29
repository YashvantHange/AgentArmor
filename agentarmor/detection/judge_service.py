"""Unified judge service — verdict (agentic) and evidence (L5) modes."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from agentarmor.detection.agentic.judge import (
    JudgeResult as VerdictJudgeResult,
)
from agentarmor.detection.agentic.judge import (
    apply_judge_to_detection,
    run_verdict_judge,
)
from agentarmor.detection.l5_judge.judge import JudgeResult as EvidenceJudgeResult
from agentarmor.detection.l5_judge.judge import judge_evidence as _judge_evidence

if TYPE_CHECKING:
    from agentarmor.core.config import AppConfig, DetectionConfig

_LEGACY_WARNED = False


def resolve_judge_mode(detection: DetectionConfig) -> str:
    """Return effective judge mode: off | uncertain_band | always."""
    judge = getattr(detection, "judge", None)
    if judge is not None and getattr(judge, "mode", None):
        return str(judge.mode)

    global _LEGACY_WARNED
    if not _LEGACY_WARNED and (detection.l5_enabled or detection.analysis_mode == "cloud"):
        warnings.warn(
            "detection.l5_enabled and detection.analysis_mode are deprecated; "
            "use detection.judge.mode (off | uncertain_band | always).",
            DeprecationWarning,
            stacklevel=3,
        )
        _LEGACY_WARNED = True

    if detection.analysis_mode == "cloud" and detection.agentic.enabled:
        return "always"
    if detection.l5_enabled:
        return "uncertain_band"
    return "off"


def should_run_verdict_judge(detection: DetectionConfig) -> bool:
    mode = resolve_judge_mode(detection)
    if mode == "always":
        return detection.analysis_mode == "cloud" and detection.agentic.enabled
    return False


def should_run_evidence_judge(detection: DetectionConfig, risk_score: float) -> bool:
    mode = resolve_judge_mode(detection)
    if mode == "off":
        return False
    if mode == "always":
        return False
    low, high = detection.confidence_judge_band
    return low < risk_score < high


async def judge_probe_verdict(
    *,
    probe_id: str,
    probe_name: str,
    attack_prompt: str,
    response: str,
    config: AppConfig,
    rubric: str | None = None,
) -> VerdictJudgeResult | None:
    if not should_run_verdict_judge(config.detection):
        return None
    return await run_verdict_judge(
        probe_id=probe_id,
        probe_name=probe_name,
        attack_prompt=attack_prompt,
        response=response,
        config=config,
        rubric=rubric,
    )


async def judge_pipeline_evidence(
    text: str,
    prompt: str,
    risk_score: float,
    detection: DetectionConfig,
) -> EvidenceJudgeResult | None:
    if not should_run_evidence_judge(detection, risk_score):
        return None
    return await _judge_evidence(text, prompt, risk_score, detection)


def apply_verdict_to_detection(
    offline_risk: float,
    offline_decision,
    judge: VerdictJudgeResult | None,
    *,
    probe_id: str = "",
    prompt: str = "",
    response: str = "",
    detection: DetectionConfig | None = None,
    fail_threshold: float = 0.7,
    warn_threshold: float = 0.4,
    l1_score: float = 0.0,
):
    judge_downgrade = True
    if detection is not None:
        judge_downgrade = detection.experimental.judge_downgrade
    return apply_judge_to_detection(
        offline_risk,
        offline_decision,
        judge,
        fail_threshold=fail_threshold,
        warn_threshold=warn_threshold,
        probe_id=probe_id,
        prompt=prompt,
        response=response,
        judge_downgrade=judge_downgrade,
        l1_score=l1_score,
    )


def judge_layers_metadata(mode: str) -> dict[str, Any]:
    return {"judge_mode": mode, "catalog_version": None}
