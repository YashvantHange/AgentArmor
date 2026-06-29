"""Detection evaluation metrics and fixture runner."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentarmor.core.config import DetectionConfig
from agentarmor.core.models import Decision, ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.detection.pipeline import analyze_probe_result


@dataclass
class CategoryMetrics:
    category: str
    total: int = 0
    correct: int = 0
    expected_fail: int = 0
    predicted_fail: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        tp = self.predicted_fail - self.false_positive
        return tp / self.predicted_fail if self.predicted_fail else 0.0

    @property
    def recall(self) -> float:
        tp = self.expected_fail - self.false_negative
        return tp / self.expected_fail if self.expected_fail else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class EvalReport:
    categories: dict[str, CategoryMetrics] = field(default_factory=dict)
    total: int = 0
    correct: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    layer_attribution: dict[str, float] = field(default_factory=dict)
    calibration_ece: float | None = None

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(self.correct / self.total, 4) if self.total else 0.0,
            "categories": {
                name: {
                    "total": m.total,
                    "correct": m.correct,
                    "accuracy": round(m.accuracy, 4),
                    "precision": round(m.precision, 4),
                    "recall": round(m.recall, 4),
                    "f1": round(m.f1, 4),
                    "false_positives": m.false_positive,
                    "false_negatives": m.false_negative,
                }
                for name, m in self.categories.items()
            },
        }
        if self.latencies_ms:
            sorted_lat = sorted(self.latencies_ms)
            payload["latency_ms"] = {
                "p50": round(_percentile(sorted_lat, 50), 2),
                "p95": round(_percentile(sorted_lat, 95), 2),
                "mean": round(statistics.mean(sorted_lat), 2),
            }
        if self.layer_attribution:
            payload["layer_attribution"] = {
                k: round(v, 2) for k, v in sorted(self.layer_attribution.items())
            }
        if self.calibration_ece is not None:
            payload["calibration_ece"] = round(self.calibration_ece, 4)
        return payload


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def load_fixture_cases(fixture_dir: Path) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []
    if not fixture_dir.exists():
        return cases
    for cat_dir in sorted(fixture_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        for path in sorted(cat_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            cases.append((cat_dir.name, data))
    return cases


def _apply_ablation(config: DetectionConfig, ablation: list[str] | None) -> DetectionConfig:
    if not ablation:
        return config
    disabled = {layer.strip().lower() for layer in ablation}
    updates: dict[str, bool] = {}
    if "l1" in disabled:
        updates["l1_enabled"] = False
    if "l2" in disabled:
        updates["l2_enabled"] = False
    if "l3" in disabled:
        updates["l3_enabled"] = False
    if "l4" in disabled:
        updates["l4_enabled"] = False
    if "meta" in disabled:
        updates["meta_enabled"] = False
    return config.model_copy(update=updates) if updates else config


def _run_case(case: dict, config: DetectionConfig) -> tuple[str, dict]:
    if case.get("error"):
        probe = ProbeResult(
            probe_id=case["probe_id"],
            probe_name=case.get("probe_name", case["probe_id"]),
            request=ProbeRequest(messages=[{"role": "user", "content": case.get("prompt", "")}]),
            response=ProbeResponse(content=case.get("response", "")),
            error=case["error"],
        )
        result = analyze_probe_result(probe, prompt_text=case.get("prompt", ""), config=config)
        return result.decision.value, result.layers

    probe = ProbeResult(
        probe_id=case["probe_id"],
        probe_name=case.get("probe_name", case["probe_id"]),
        request=ProbeRequest(messages=[{"role": "user", "content": case["prompt"]}]),
        response=ProbeResponse(content=case["response"]),
    )
    result = analyze_probe_result(probe, prompt_text=case["prompt"], config=config)
    return result.decision.value, result.layers


def _accumulate_layer_attribution(layers: dict, totals: dict[str, float]) -> None:
    mapping = {
        "l1": "l1",
        "l2": "l2",
        "l3": "l3",
        "l4": "l4",
        "meta": "meta",
        "echo_strip": "echo",
    }
    for key, label in mapping.items():
        block = layers.get(key)
        if not isinstance(block, dict):
            continue
        if key == "l2":
            score = float(block.get("max_score", 0))
        elif key == "echo_strip":
            score = float(block.get("latency_ms", 0))
            totals[label] = totals.get(label, 0) + score
            continue
        else:
            score = float(block.get("score", block.get("risk_score", 0)))
        totals[label] = totals.get(label, 0) + score * 100


def _total_latency_ms(layers: dict) -> float:
    total = 0.0
    for key in ("echo_strip", "l1", "l2", "l3", "l4", "meta"):
        block = layers.get(key)
        if isinstance(block, dict) and "latency_ms" in block:
            total += float(block["latency_ms"])
    return total


def evaluate_detection_fixtures(
    fixture_dir: Path,
    config: DetectionConfig | None = None,
    *,
    ablation: list[str] | None = None,
) -> EvalReport:
    cfg = _apply_ablation(config or DetectionConfig(), ablation)
    report = EvalReport()
    fail_expected = {"FAIL", "WARN"}

    for category, case in load_fixture_cases(fixture_dir):
        expected = case["expected_decision"]
        predicted, layers = _run_case(case, cfg)

        if category not in report.categories:
            report.categories[category] = CategoryMetrics(category=category)
        m = report.categories[category]
        m.total += 1
        report.total += 1

        if predicted == expected:
            m.correct += 1
            report.correct += 1

        exp_fail = expected in fail_expected
        pred_fail = predicted in fail_expected
        if exp_fail:
            m.expected_fail += 1
        if pred_fail:
            m.predicted_fail += 1
        if not exp_fail and pred_fail:
            m.false_positive += 1
        if exp_fail and not pred_fail:
            m.false_negative += 1

        report.latencies_ms.append(_total_latency_ms(layers))
        _accumulate_layer_attribution(layers, report.layer_attribution)

    return report


def compare_baseline(report: EvalReport, baseline_path: Path) -> dict:
    if not baseline_path.exists():
        return {"error": f"baseline not found: {baseline_path}"}
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    delta: dict[str, dict] = {}
    for cat, metrics in report.categories.items():
        base_cat = (baseline.get("categories") or {}).get(cat, {})
        delta[cat] = {
            "accuracy_delta": round(metrics.accuracy - float(base_cat.get("accuracy", 0)), 4),
            "fp_delta": metrics.false_positive - int(base_cat.get("false_positives", 0)),
            "fn_delta": metrics.false_negative - int(base_cat.get("false_negatives", 0)),
        }
    baseline_fp = sum(
        int((baseline.get("categories") or {}).get(c, {}).get("false_positives", 0))
        for c in (baseline.get("categories") or {})
    )
    current_fp = sum(m.false_positive for m in report.categories.values())
    fp_reduction_pct = 0.0
    if baseline_fp:
        fp_reduction_pct = round((baseline_fp - current_fp) / baseline_fp * 100, 1)

    return {
        "baseline_accuracy": baseline.get("accuracy"),
        "current_accuracy": round(report.correct / report.total, 4) if report.total else 0,
        "false_positive_reduction_pct": fp_reduction_pct,
        "categories": delta,
    }


def load_calibration_ece(model_dir: str | Path) -> float | None:
    from agentarmor.detection.meta.calibration import calibration_path_for_model_dir, load_calibration

    cal = load_calibration(calibration_path_for_model_dir(model_dir))
    return cal.ece if cal else None
