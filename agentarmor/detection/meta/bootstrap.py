"""Bootstrap meta classifier — JSON linear weights (always) + optional XGBoost."""

from __future__ import annotations

import json
from pathlib import Path

FEATURE_ORDER = [
    "l1",
    "l2_max",
    "l2_prompt_injection",
    "l2_data_leakage",
    "l2_jailbreak",
    "l2_tool_abuse",
    "l2_unsafe_output",
    "l3",
    "l4",
]

# Hand-tuned linear weights for bootstrap meta scoring
LINEAR_WEIGHTS = {
    "l1": 0.28,
    "l2_max": 0.22,
    "l2_prompt_injection": 0.08,
    "l2_data_leakage": 0.10,
    "l2_jailbreak": 0.10,
    "l2_tool_abuse": 0.06,
    "l2_unsafe_output": 0.06,
    "l3": 0.14,
    "l4": 0.16,
}
LINEAR_BIAS = -0.08


def meta_json_path(xgb_path: Path) -> Path:
    return xgb_path.with_suffix(".json")


def ensure_meta_model(path: Path) -> None:
    json_path = meta_json_path(path)
    if path.exists() or json_path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _save_linear_json(json_path)
    _try_train_xgb(path)


def _save_linear_json(path: Path) -> None:
    payload = {
        "type": "linear",
        "features": FEATURE_ORDER,
        "weights": LINEAR_WEIGHTS,
        "bias": LINEAR_BIAS,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _try_train_xgb(path: Path) -> None:
    try:
        import numpy as np
        import xgboost as xgb

        rng = np.random.default_rng(42)
        n = 500
        X = rng.random((n, len(FEATURE_ORDER)))
        risk = (
            0.35 * X[:, 0]
            + 0.25 * X[:, 1]
            + 0.1 * X[:, 2:7].max(axis=1)
            + 0.2 * X[:, 7]
            + 0.2 * X[:, 8]
            + rng.normal(0, 0.05, n)
        )
        y = (risk > 0.55).astype(int)
        dtrain = xgb.DMatrix(X, label=y, feature_names=FEATURE_ORDER)
        params = {"objective": "binary:logistic", "max_depth": 4, "eta": 0.2}
        booster = xgb.train(params, dtrain, num_boost_round=30)
        booster.save_model(str(path))
    except Exception:
        pass


def predict_linear(features: list[float], json_path: Path) -> float:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    weights = data["weights"]
    bias = float(data.get("bias", 0))
    names = data.get("features", FEATURE_ORDER)
    total = bias
    for name, value in zip(names, features):
        total += float(weights.get(name, 0)) * value
    return min(max(total, 0.0), 1.0)
