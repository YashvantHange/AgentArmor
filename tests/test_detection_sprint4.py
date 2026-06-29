"""Sprint 4 tests — probe thresholds, calibration, fusion, eval extensions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentarmor.core.config import ConfidenceFusionConfig, DetectionConfig, ProbeThresholdEntry
from agentarmor.detection.confidence_fusion import fuse_detection_confidence
from agentarmor.detection.eval import compare_baseline, evaluate_detection_fixtures
from agentarmor.detection.meta.calibration import PlattCalibration, fit_platt
from agentarmor.detection.probe_thresholds import resolve_probe_thresholds
from agentarmor.detection.meta.xgb_scorer import score_meta
from agentarmor.detection.l1_signatures import L1Result
from agentarmor.detection.l2_classifier.fallback import L2Result
from agentarmor.detection.l3_semantic.faiss_index import L3Result
from agentarmor.detection.l4_structural import L4Result


def test_probe_thresholds_l1_preset():
    thr = resolve_probe_thresholds("l1.ignore-instructions")
    assert thr.fail_threshold == 0.65
    assert thr.warn_threshold == 0.35
    assert thr.refusal_escalation == 0.55
    assert thr.pattern == "l1.*"


def test_probe_thresholds_custom_override():
    cfg = DetectionConfig(
        probe_thresholds={
            "l1.*": ProbeThresholdEntry(
                fail_threshold=0.60,
                warn_threshold=0.30,
                refusal_escalation=0.50,
            )
        }
    )
    thr = resolve_probe_thresholds("l1.reveal-system-prompt", cfg)
    assert thr.fail_threshold == 0.60


def test_meta_uses_per_probe_thresholds():
    cfg = DetectionConfig()
    l1 = L1Result(score=0.9, matches=["x"], categories=["system_exposure"], engine="fallback")
    l2 = L2Result()
    l3 = L3Result(score=0.0, matches=[])
    l4 = L4Result(score=0.85, components={"outcomes": 0.85}, evidence=[])
    result = score_meta(l1, l2, l3, l4, cfg, probe_id="l1.ignore-instructions")
    assert result.decision.value == "FAIL"


def test_platt_fit_produces_valid_params():
    scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9] * 20
    labels = [0, 0, 0, 1, 1, 1] * 20
    cal = fit_platt(scores, labels)
    assert cal.a != 0.0
    assert 0.0 <= cal.apply(0.5) <= 1.0


def test_platt_apply_monotonic():
    cal = PlattCalibration(method="platt", a=2.0, b=-1.0)
    assert cal.apply(0.2) < cal.apply(0.8)


def test_confidence_fusion_floor_only_on_hard_signal():
    low = fuse_detection_confidence(
        risk_score=0.9,
        decision_fail=True,
        detection_layers={"meta": {"confidence": 0.2}},
        judge_confidence=0.1,
        has_hard_outcome=False,
        judge_confirms_vuln=False,
    )
    high = fuse_detection_confidence(
        risk_score=0.9,
        decision_fail=True,
        detection_layers={"meta": {"confidence": 0.2}},
        judge_confidence=0.1,
        has_hard_outcome=True,
        judge_confirms_vuln=False,
    )
    assert low["fused_confidence"] < high["fused_confidence"]


def test_confidence_fusion_custom_weights():
    weights = ConfidenceFusionConfig(rules=0.0, pipeline=1.0, judge=0.0, meta=0.0)
    result = fuse_detection_confidence(
        risk_score=0.5,
        decision_fail=False,
        detection_layers={"l1": {"score": 0.9}},
        fusion_weights=weights,
    )
    assert result["fused_confidence"] >= 0.8


def test_eval_includes_latency_and_attribution():
    fixture_dir = Path("tests/fixtures/detection")
    report = evaluate_detection_fixtures(fixture_dir, DetectionConfig())
    payload = report.to_dict()
    assert "latency_ms" in payload
    assert payload["latency_ms"]["p50"] >= 0
    assert "layer_attribution" in payload


def test_eval_ablation_disables_l1():
    fixture_dir = Path("tests/fixtures/detection")
    full = evaluate_detection_fixtures(fixture_dir, DetectionConfig())
    ablated = evaluate_detection_fixtures(fixture_dir, DetectionConfig(), ablation=["l1"])
    assert full.total == ablated.total


def test_compare_baseline_fp_reduction():
    from agentarmor.detection.eval import CategoryMetrics, EvalReport

    report = EvalReport(
        categories={
            "echo_refusal": CategoryMetrics(category="echo_refusal", total=10, correct=10),
        },
        total=10,
        correct=10,
    )
    baseline_path = Path("docs/detection_baseline_v1.3.0.json")
    if baseline_path.exists():
        cmp = compare_baseline(report, baseline_path)
        assert "false_positive_reduction_pct" in cmp
