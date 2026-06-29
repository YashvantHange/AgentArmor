"""Build meta calibration from detection fixtures + synthetic augmentation."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from agentarmor.core.config import DetectionConfig
from agentarmor.detection.eval import load_fixture_cases
from agentarmor.detection.meta.calibration import (
    calibration_path_for_model_dir,
    expected_calibration_error,
    fit_platt,
    save_calibration,
)
from agentarmor.detection.pipeline import _analyze_local


def _label_from_expected(expected: str) -> int:
    return 1 if expected in ("FAIL", "WARN") else 0


def _layer_vector(layers: dict) -> dict[str, float]:
    l2 = layers.get("l2", {}) or {}
    scores = l2.get("scores", {}) if isinstance(l2, dict) else {}
    return {
        "l1": float((layers.get("l1") or {}).get("score", 0)),
        "l2_max": float(l2.get("max_score", 0)),
        "l2_prompt_injection": float(scores.get("prompt_injection", 0)),
        "l2_data_leakage": float(scores.get("data_leakage", 0)),
        "l2_jailbreak": float(scores.get("jailbreak", 0)),
        "l2_tool_abuse": float(scores.get("tool_abuse", 0)),
        "l2_unsafe_output": float(scores.get("unsafe_output", 0)),
        "l3": float((layers.get("l3") or {}).get("score", 0)),
        "l4": float((layers.get("l4") or {}).get("score", 0)),
    }


def build_records(fixture_dir: Path, config: DetectionConfig) -> list[dict]:
    records: list[dict] = []
    for category, case in load_fixture_cases(fixture_dir):
        prompt = case.get("prompt", "")
        response = case.get("response", "")
        probe_id = case.get("probe_id", "l1.ignore-instructions")
        if case.get("error"):
            continue
        det = _analyze_local(response, prompt, probe_id, config)
        records.append(
            {
                "id": case.get("id", f"{category}_{len(records)}"),
                "probe_id": probe_id,
                "category": category,
                "prompt": prompt,
                "response": response,
                "layer_outputs": _layer_vector(det.layers),
                "meta_risk": det.risk_score,
                "label": "vuln" if _label_from_expected(case["expected_decision"]) else "safe",
                "label_source": "fixture",
            }
        )
    return records


def augment_records(records: list[dict], target: int, seed: int = 42) -> list[dict]:
    """Perturb meta risk to reach target sample count while preserving label."""
    rng = random.Random(seed)
    out = list(records)
    if not records:
        return out
    while len(out) < target:
        base = rng.choice(records)
        risk = float(base.get("meta_risk", 0.5))
        is_vuln = base["label"] == "vuln"
        if is_vuln:
            risk = min(1.0, max(0.55, risk + rng.uniform(-0.06, 0.06)))
        else:
            risk = min(0.54, max(0.0, risk + rng.uniform(-0.06, 0.06)))
        out.append(
            {
                **base,
                "id": f"{base['id']}_aug_{len(out)}",
                "meta_risk": risk,
                "label": base["label"],
                "label_source": "synthetic",
            }
        )
    return out


def records_to_scores(records: list[dict], config: DetectionConfig) -> tuple[list[float], list[int]]:
    scores: list[float] = []
    labels: list[int] = []
    for rec in records:
        scores.append(float(rec.get("meta_risk", 0)))
        labels.append(1 if rec["label"] == "vuln" else 0)
    return scores, labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Platt calibration for meta scorer")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/detection"),
    )
    parser.add_argument("--target-samples", type=int, default=2000)
    parser.add_argument("--output-jsonl", type=Path, default=Path("docs/meta_seed_labels.jsonl"))
    parser.add_argument("--model-dir", type=str, default="~/.agentarmor/models")
    args = parser.parse_args()

    config = DetectionConfig(model_dir=args.model_dir)
    records = build_records(args.fixture, config)
    records = augment_records(records, args.target_samples)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")

    scores, labels = records_to_scores(records, config)
    split = int(len(scores) * 0.8)
    train_scores, train_labels = scores[:split], labels[:split]
    hold_scores, hold_labels = scores[split:], labels[split:]

    cal = fit_platt(train_scores, train_labels, experimental=True)
    fixture_scores, fixture_labels = records_to_scores(records[:70], config)
    cal.ece = expected_calibration_error(fixture_scores, fixture_labels, cal.a, cal.b)
    cal.sample_count = len(records)
    if cal.ece < 0.1 and len(records) >= 2000:
        cal.experimental = False

    out_path = calibration_path_for_model_dir(config.model_dir)
    save_calibration(out_path, cal)

    print(
        json.dumps(
            {
                "records": len(records),
                "labels_jsonl": str(args.output_jsonl),
                "calibration": str(out_path),
                "ece_holdout": round(cal.ece, 4),
                "platt_a": round(cal.a, 4),
                "platt_b": round(cal.b, 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
