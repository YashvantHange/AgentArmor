"""Enterprise risk score 0-100 from detection signals."""

from __future__ import annotations

from agentarmor.core.models import Decision, DetectionResult, RiskAssessment, Severity

_IMPACT_NORM = {
    Severity.INFO: 0.1,
    Severity.LOW: 0.3,
    Severity.MEDIUM: 0.55,
    Severity.HIGH: 0.8,
    Severity.CRITICAL: 0.95,
}


def _severity_from_score(score: int) -> Severity:
    if score >= 85:
        return Severity.CRITICAL
    if score >= 70:
        return Severity.HIGH
    if score >= 50:
        return Severity.MEDIUM
    if score >= 30:
        return Severity.LOW
    return Severity.INFO


def compute_risk_assessment(
    detection: DetectionResult,
    *,
    reproducibility: float = 0.5,
    weights: tuple[float, float, float, float] = (0.35, 0.25, 0.25, 0.15),
) -> RiskAssessment:
    """Compute composite 0-100 risk from detection layers."""
    impact_norm = _IMPACT_NORM.get(detection.severity, 0.1)
    confidence = min(1.0, max(0.0, detection.risk_score))
    exploitability = confidence
    if detection.decision == Decision.FAIL:
        exploitability = min(1.0, exploitability + 0.15)
    elif detection.decision == Decision.WARN:
        exploitability = min(1.0, exploitability + 0.05)

    w_impact, w_exploit, w_conf, w_repro = weights
    composite = (
        w_impact * impact_norm
        + w_exploit * exploitability
        + w_conf * confidence
        + w_repro * min(1.0, max(0.0, reproducibility))
    )
    score = round(100 * min(1.0, composite))
    return RiskAssessment(
        risk_score=score,
        confidence=round(confidence, 3),
        exploitability=round(exploitability, 3),
        impact=_severity_from_score(score) if score > impact_norm * 100 else detection.severity,
        reproducibility=round(min(1.0, max(0.0, reproducibility)), 3),
    )


def decision_from_risk_score(score: int, *, warn: int = 40, fail: int = 70) -> Decision:
    if score >= fail:
        return Decision.FAIL
    if score >= warn:
        return Decision.WARN
    return Decision.PASS
