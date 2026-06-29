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
    *,
    probe_id: str = "",
) -> MetaResult:
    import time

    start = time.perf_counter()

    if config.meta_enabled:
        features = _feature_vector(l1, l2, l3, l4)
        from agentarmor.detection.models.manager import get_model_manager

        manager = get_model_manager(config.model_dir)
        manager.ensure_bootstrap_models()

        if manager.meta_model_path().exists() and not config.meta_xgb_experimental:
            try:
                result = _score_xgb(features, config, l1, l2, l3, l4, probe_id=probe_id)
                result.latency_ms = (time.perf_counter() - start) * 1000
                return result
            except Exception:
                pass
        try:
            result = _score_linear(features, config, l1, l2, l3, l4, probe_id=probe_id)
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception:
            pass

    result = _score_fusion_fallback(l1, l2, l3, l4, config, probe_id=probe_id)
    result = _apply_hard_signal_floor(result, l1, l2, l3, l4, config)
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


def _hard_signal_floor(
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
) -> float:
    """Minimum risk when layer signals are unambiguous (guards synthetic meta under-scoring)."""
    floor = 0.0
    outcomes = float(l4.components.get("outcomes", 0.0))
    hierarchy = float(l4.components.get("hierarchy", 0.0))
    if outcomes >= 0.8:
        floor = max(floor, 0.85)
    if hierarchy >= 0.85:
        floor = max(floor, 0.8)
    if l4.score >= 0.85:
        floor = max(floor, 0.8)
    if l1.score >= 0.85:
        floor = max(floor, 0.75)
    if l1.score >= 0.75 and l4.score >= 0.75:
        floor = max(floor, 0.55)
    boundary = float(l4.components.get("boundary", 0.0))
    if l1.score >= 0.75 and boundary >= 0.8:
        floor = max(floor, 0.55)
    if l2.max_score >= 0.85:
        floor = max(floor, 0.72)
    if l3.score >= 0.9:
        floor = max(floor, 0.75)
    return floor


def _apply_hard_signal_floor(
    result: MetaResult,
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    config: DetectionConfig,
) -> MetaResult:
    floor = _hard_signal_floor(l1, l2, l3, l4)
    if floor <= result.risk_score:
        return result
    return _risk_to_meta(max(result.risk_score, floor), config, engine=result.engine)


def _apply_calibration(risk: float, config: DetectionConfig) -> float:
    if not config.meta_calibration_enabled:
        return risk
    from agentarmor.detection.meta.calibration import calibration_path_for_model_dir, load_calibration

    cal_path = calibration_path_for_model_dir(config.model_dir)
    cal = load_calibration(cal_path)
    if cal is None or cal.experimental:
        return risk
    return cal.apply(risk)


def _score_xgb(
    features: list[float],
    config: DetectionConfig,
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    *,
    probe_id: str = "",
) -> MetaResult:
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
    risk = _apply_calibration(risk, config)
    result = _risk_to_meta(risk, config, engine="xgboost", probe_id=probe_id)
    return _apply_hard_signal_floor(result, l1, l2, l3, l4, config)


def _score_linear(
    features: list[float],
    config: DetectionConfig,
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    *,
    probe_id: str = "",
) -> MetaResult:
    from agentarmor.detection.models.manager import get_model_manager

    manager = get_model_manager(config.model_dir)
    json_path = meta_json_path(manager.meta_model_path())
    if not json_path.exists():
        raise FileNotFoundError("linear meta model missing")
    risk = predict_linear(features, json_path)
    risk = _apply_calibration(risk, config)
    result = _risk_to_meta(risk, config, engine="linear_meta", probe_id=probe_id)
    return _apply_hard_signal_floor(result, l1, l2, l3, l4, config)


def _score_fusion_fallback(
    l1: L1Result,
    l2: L2Result,
    l3: L3Result,
    l4: L4Result,
    config: DetectionConfig,
    *,
    probe_id: str = "",
) -> MetaResult:
    weights = config.fusion_weights
    w_total = weights.l1 + weights.l4 + 0.2 + 0.2
    risk = (
        weights.l1 * l1.score
        + weights.l4 * l4.score
        + 0.2 * l2.max_score
        + 0.2 * l3.score
    ) / w_total
    risk = _apply_calibration(risk, config)
    return _risk_to_meta(risk, config, engine="fusion_fallback", probe_id=probe_id)


def _risk_to_meta(
    risk: float,
    config: DetectionConfig,
    engine: str,
    *,
    probe_id: str = "",
) -> MetaResult:
    from agentarmor.detection.probe_thresholds import resolve_probe_thresholds

    thresholds = resolve_probe_thresholds(probe_id, config) if probe_id else None
    fail_thr = thresholds.fail_threshold if thresholds else config.fail_threshold
    warn_thr = thresholds.warn_threshold if thresholds else config.warn_threshold

    risk = min(max(risk, 0.0), 1.0)
    confidence = abs(risk - 0.5) * 2

    if risk >= fail_thr:
        severity = Severity.CRITICAL if risk >= 0.85 else Severity.HIGH
        decision = Decision.FAIL
    elif risk >= warn_thr:
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
