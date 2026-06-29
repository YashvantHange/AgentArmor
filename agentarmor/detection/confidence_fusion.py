"""Fuse multi-layer detection signals into a single confidence score."""

from __future__ import annotations

from typing import Any

# Weights per plan: rules 0.2, L1-L4 0.3, judge 0.3, cloud/meta 0.2
FUSION_WEIGHTS = {
    "rules": 0.2,
    "pipeline": 0.3,
    "judge": 0.3,
    "meta": 0.2,
}


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
) -> dict[str, Any]:
    """
    Blend rules, pipeline meta, judge, and assertion scores.
    Returns fused score 0-1 plus per-source breakdown.
    """
    layers = detection_layers or {}

    rules_score = _layer_score(layers, "assertions", risk_score if decision_fail else 0.0)
    pipeline_score = _layer_score(layers, "meta", risk_score)
    if pipeline_score == 0.0:
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

    fused = (
        FUSION_WEIGHTS["rules"] * min(1.0, rules_score)
        + FUSION_WEIGHTS["pipeline"] * min(1.0, pipeline_score)
        + FUSION_WEIGHTS["judge"] * min(1.0, judge_score)
        + FUSION_WEIGHTS["meta"] * min(1.0, meta_score)
    )
    if decision_fail and fused < 0.5:
        fused = max(fused, min(1.0, risk_score))

    return {
        "fused_confidence": round(min(1.0, max(0.0, fused)), 3),
        "fusion_breakdown": {
            "rules": round(rules_score, 3),
            "pipeline": round(pipeline_score, 3),
            "judge": round(judge_score, 3),
            "meta": round(meta_score, 3),
        },
        "fusion_weights": dict(FUSION_WEIGHTS),
    }
