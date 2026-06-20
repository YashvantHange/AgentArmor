"""Meta scorer — XGBoost when available, else bootstrap linear JSON, else fusion."""

from __future__ import annotations

from dataclasses import dataclass

from agentarmor.core.config import DetectionConfig
from agentarmor.core.models import Decision, Severity
from agentarmor.detection.l2_classifier.fallback import L2Result
from agentarmor.detection.l4_structural import L4Result
from agentarmor.detection.l1_signatures import L1Result
from agentarmor.detection.l3_semantic.faiss_index import L3Result
from agentarmor.detection.meta.bootstrap import FEATURE_ORDER, meta_json_path, predict_linear


@dataclass
class MetaResult:
    risk_score: float
    severity: Severity
    decision: Decision
    confidence: float
    engine: str = "meta"
    latency_ms: float = 0.0


def score_meta(
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    config: DetectionConfig,
) -> MetaResult:
    import time

    start = time.perf_counter()

    if config.meta_enabled:
        features = _feature_vector(l1, l2, l3, l4)
        from agentarmor.detection.models.manager import get_model_manager

        manager = get_model_manager(config.model_dir)
        manager.ensure_bootstrap_models()

        if manager.meta_model_path().exists():
            try:
                result = _score_xgb(features, config)
                result.latency_ms = (time.perf_counter() - start) * 1000
                return result
            except Exception:
                pass
        try:
            result = _score_linear(features, config)
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception:
            pass

    result = _score_fusion_fallback(l1, l2, l3, l4, config)
    result.latency_ms = (time.perf_counter() - start) * 1000
    result.engine = "fusion_fallback"
    return result


def _feature_vector(l1: L1Result, l2: L2Result, l3: L3Result, l4: L4Result) -> list[float]:
    return [
        l1.score,
        l2.max_score,
        l2.scores.get("prompt_injection", 0.0),
        l2.scores.get("data_leakage", 0.0),
        l2.scores.get("jailbreak", 0.0),
        l2.scores.get("tool_abuse", 0.0),
        l2.scores.get("unsafe_output", 0.0),
        l3.score,
        l4.score,
    ]


def _score_xgb(features: list[float], config: DetectionConfig) -> MetaResult:
    import xgboost as xgb

    from agentarmor.detection.models.manager import get_model_manager

    manager = get_model_manager(config.model_dir)
    model_path = manager.meta_model_path()
    if not model_path.exists():
        raise FileNotFoundError("xgb model missing")

    booster = xgb.Booster()
    booster.load_model(str(model_path))
    dmat = xgb.DMatrix([features], feature_names=FEATURE_ORDER)
    risk = float(booster.predict(dmat)[0])
    return _risk_to_meta(risk, config, engine="xgboost")


def _score_linear(features: list[float], config: DetectionConfig) -> MetaResult:
    from agentarmor.detection.models.manager import get_model_manager

    manager = get_model_manager(config.model_dir)
    json_path = meta_json_path(manager.meta_model_path())
    if not json_path.exists():
        raise FileNotFoundError("linear meta model missing")
    risk = predict_linear(features, json_path)
    return _risk_to_meta(risk, config, engine="linear_meta")


def _score_fusion_fallback(
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    config: DetectionConfig,
) -> MetaResult:
    weights = config.fusion_weights
    w_total = weights.l1 + weights.l4 + 0.2 + 0.2
    risk = (
        weights.l1 * l1.score
        + weights.l4 * l4.score
        + 0.2 * l2.max_score
        + 0.2 * l3.score
    ) / w_total
    return _risk_to_meta(risk, config, engine="fusion_fallback")


def _risk_to_meta(risk: float, config: DetectionConfig, engine: str) -> MetaResult:
    risk = min(max(risk, 0.0), 1.0)
    confidence = abs(risk - 0.5) * 2

    if risk >= config.fail_threshold:
        severity = Severity.CRITICAL if risk >= 0.85 else Severity.HIGH
        decision = Decision.FAIL
    elif risk >= config.warn_threshold:
        severity = Severity.MEDIUM if risk >= 0.55 else Severity.LOW
        decision = Decision.WARN
    else:
        severity = Severity.INFO
        decision = Decision.PASS

    return MetaResult(
        risk_score=risk,
        severity=severity,
        decision=decision,
        confidence=confidence,
        engine=engine,
    )
