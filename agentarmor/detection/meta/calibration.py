"""Probability calibration for meta risk scores (Platt scaling)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlattCalibration:
    """Maps raw risk score to calibrated probability via sigmoid(a*x + b)."""

    method: str
    a: float
    b: float
    ece: float = 0.0
    sample_count: int = 0
    experimental: bool = True

    def apply(self, raw_score: float) -> float:
        z = self.a * raw_score + self.b
        return _sigmoid(z)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "a": self.a,
            "b": self.b,
            "ece": round(self.ece, 4),
            "sample_count": self.sample_count,
            "experimental": self.experimental,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlattCalibration:
        return cls(
            method=str(data.get("method", "platt")),
            a=float(data.get("a", 1.0)),
            b=float(data.get("b", 0.0)),
            ece=float(data.get("ece", 0.0)),
            sample_count=int(data.get("sample_count", 0)),
            experimental=bool(data.get("experimental", True)),
        )


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def load_calibration(path: Path) -> PlattCalibration | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return PlattCalibration.from_dict(data)


def save_calibration(path: Path, cal: PlattCalibration) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cal.to_dict(), indent=2), encoding="utf-8")


def fit_platt(
    scores: list[float],
    labels: list[int],
    *,
    experimental: bool = True,
) -> PlattCalibration:
    """Fit Platt scaling with simple gradient descent (no sklearn dependency)."""
    if len(scores) != len(labels) or not scores:
        return PlattCalibration(method="platt", a=1.0, b=0.0, experimental=experimental)

    a, b = 1.0, 0.0
    lr = 0.05
    for _ in range(400):
        grad_a = 0.0
        grad_b = 0.0
        for x, y in zip(scores, labels):
            p = _sigmoid(a * x + b)
            err = p - y
            grad_a += err * x
            grad_b += err
        n = len(scores)
        a -= lr * grad_a / n
        b -= lr * grad_b / n

    ece = expected_calibration_error(scores, labels, a, b)
    return PlattCalibration(
        method="platt",
        a=a,
        b=b,
        ece=ece,
        sample_count=len(scores),
        experimental=experimental,
    )


def expected_calibration_error(
    scores: list[float],
    labels: list[int],
    a: float,
    b: float,
    *,
    n_bins: int = 10,
) -> float:
    """Expected calibration error on held-out style binning."""
    if not scores:
        return 0.0
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for x, y in zip(scores, labels):
        p = _sigmoid(a * x + b)
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, y))

    total = len(scores)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        avg_y = sum(y for _, y in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(avg_p - avg_y)
    return ece


def calibration_path_for_model_dir(model_dir: str | Path) -> Path:
    from agentarmor.detection.models.manager import resolve_model_dir

    return resolve_model_dir(model_dir) / "calibration.json"
