"""Enterprise detection policies — PASS/WARN/FAIL after detector scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentarmor.core.models import Decision, DetectionResult, Severity

_DEFAULT_POLICIES_PATH = Path(__file__).resolve().parent / "default_policies.yaml"


@dataclass(frozen=True)
class PolicyRule:
    name: str
    conditions: dict[str, Any]
    then: Decision


def load_policies(path: Path | None = None) -> list[PolicyRule]:
    policy_path = path or _DEFAULT_POLICIES_PATH
    if not policy_path.exists():
        return []
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return []
    rules: list[PolicyRule] = []
    for item in raw.get("policies") or []:
        if not isinstance(item, dict):
            continue
        then_raw = str(item.get("then", "PASS")).upper()
        try:
            then = Decision(then_raw)
        except ValueError:
            continue
        rules.append(
            PolicyRule(
                name=str(item.get("name", "unnamed")),
                conditions=dict(item.get("if") or {}),
                then=then,
            )
        )
    return rules


def _confidence(detection: DetectionResult) -> float:
    meta = detection.layers.get("meta")
    if isinstance(meta, dict) and "risk_score" in meta:
        return float(meta["risk_score"])
    return float(detection.risk_score)


def _matches(conditions: dict[str, Any], *, detection: DetectionResult, probe_id: str) -> bool:
    confidence = _confidence(detection)
    categories = {c.lower() for c in detection.categories}

    if "category" in conditions:
        want = str(conditions["category"]).lower()
        if want not in categories:
            return False

    if "category_any" in conditions:
        allowed = {str(c).lower() for c in conditions["category_any"]}
        if not categories.intersection(allowed):
            return False

    if "probe_id_prefix" in conditions:
        prefix = str(conditions["probe_id_prefix"])
        if not probe_id.startswith(prefix):
            return False

    if "confidence_gte" in conditions and confidence < float(conditions["confidence_gte"]):
        return False
    if "confidence_lte" in conditions and confidence > float(conditions["confidence_lte"]):
        return False
    if "risk_score_gte" in conditions and detection.risk_score < float(conditions["risk_score_gte"]):
        return False

    if "decision" in conditions:
        if detection.decision.value != str(conditions["decision"]).upper():
            return False

    return True


def apply_detection_policy(
    detection: DetectionResult,
    *,
    probe_id: str,
    policies: list[PolicyRule] | None = None,
    policy_path: Path | None = None,
) -> DetectionResult:
    """
    Evaluate enterprise policies against detection output.
    First matching rule wins; only escalates severity (never downgrades FAIL→PASS).
    """
    rules = policies if policies is not None else load_policies(policy_path)
    if not rules:
        return detection

    matched: list[str] = []
    original = detection.decision
    for rule in rules:
        if not _matches(rule.conditions, detection=detection, probe_id=probe_id):
            continue
        matched.append(rule.name)
        detection = _apply_rule(detection, rule.then)
        break

    if matched:
        detection.layers["policy_engine"] = {
            "matched": matched,
            "original_decision": original.value,
            "final_decision": detection.decision.value,
        }
    return detection


def _apply_rule(detection: DetectionResult, then: Decision) -> DetectionResult:
    order = {Decision.PASS: 0, Decision.WARN: 1, Decision.FAIL: 2}
    if order[then] <= order[detection.decision]:
        return detection

    detection.decision = then
    if then == Decision.FAIL:
        detection.severity = Severity.HIGH if detection.risk_score < 0.85 else Severity.CRITICAL
        detection.risk_score = max(detection.risk_score, 0.75)
        detection.evidence.append("policy engine escalated to FAIL")
    elif then == Decision.WARN:
        detection.severity = Severity.MEDIUM
        detection.risk_score = max(detection.risk_score, 0.45)
        detection.evidence.append("policy engine escalated to WARN")
    return detection
