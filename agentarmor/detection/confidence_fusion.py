"""Confidence fusion — blend rules, pipeline, judge, and meta signals."""

from __future__ import annotations

from typing import Any

from agentarmor.core.config import ConfidenceFusionConfig


def _layer_score(layers: dict[str, Any], key: str, default: float = 0.0) -> float:
    block = layers.get(key)
    if not isinstance(block, dict):
        return default
    if "score" in block:
        return float(block["score"])
    if "confidence" in block:
        return float(block["confidence"])
    if key == "l5_judge" and block.get("vulnerable"):
        return float(block.get("confidence", 0.8))
    return default


def fuse_detection_confidence(
    *,
    risk_score: float,
    decision_fail: bool,
    detection_layers: dict[str, Any] | None,
    judge_confidence: float | None = None,
    fusion_weights: ConfidenceFusionConfig | None = None,
    has_hard_outcome: bool = False,
    judge_confirms_vuln: bool = False,
) -> dict[str, Any]:
    """
    Blend rules, pipeline meta, judge, and assertion scores.
    Returns fused score 0-1 plus per-source breakdown.
    """
    weights = fusion_weights or ConfidenceFusionConfig()
    layers = detection_layers or {}

    rules_score = _layer_score(layers, "assertions", risk_score if decision_fail else 0.0)

    meta_block = layers.get("meta")
    if isinstance(meta_block, dict):
        pipeline_score = _layer_score(layers, "meta", 0.0)
    else:
        pipeline_score = 0.0
        for key in ("l1", "l2", "l3", "l4", "semantic"):
            s = _layer_score(layers, key, 0.0)
            if s > pipeline_score:
                pipeline_score = s
        if pipeline_score == 0.0:
            pipeline_score = risk_score

    judge_score = judge_confidence if judge_confidence is not None else _layer_score(
        layers, "l5_judge", 0.0
    )
    meta_score = _layer_score(layers, "meta", pipeline_score)

    w_total = weights.rules + weights.pipeline + weights.judge + weights.meta
    if w_total <= 0:
        w_total = 1.0

    fused = (
        weights.rules * min(1.0, rules_score)
        + weights.pipeline * min(1.0, pipeline_score)
        + weights.judge * min(1.0, judge_score)
        + weights.meta * min(1.0, meta_score)
    ) / w_total

    if decision_fail and fused < 0.5 and (has_hard_outcome or judge_confirms_vuln):
        fused = max(fused, min(1.0, risk_score))

    return {
        "fused_confidence": round(min(1.0, max(0.0, fused)), 3),
        "fusion_breakdown": {
            "rules": round(rules_score, 3),
            "pipeline": round(pipeline_score, 3),
            "judge": round(judge_score, 3),
            "meta": round(meta_score, 3),
        },
        "fusion_weights": {
            "rules": weights.rules,
            "pipeline": weights.pipeline,
            "judge": weights.judge,
            "meta": weights.meta,
        },
    }
