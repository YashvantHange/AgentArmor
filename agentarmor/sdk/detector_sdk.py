"""Custom Detector SDK — public API for community detector authors."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentarmor.plugins.base import BaseDetector, register

Detector = BaseDetector
MAX_RISK_DELTA = 0.15


def register_detector(cls: type[BaseDetector]) -> type[BaseDetector]:
    return register("detector")(cls)


@dataclass
class LayerContribution:
    detector_id: str
    risk_delta: float
    evidence: str
    trust: str
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector_id": self.detector_id,
            "risk_delta": round(self.risk_delta, 4),
            "evidence": self.evidence,
            "trust": self.trust,
            "latency_ms": round(self.latency_ms, 2),
        }


def validate_detector_module(path: Path) -> list[str]:
    """Static validation for detector modules before marketplace install."""
    errors: list[str] = []
    if not path.exists():
        return [f"file not found: {path}"]
    if path.suffix != ".py":
        errors.append("detector must be a .py file")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]

    has_detector = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = getattr(base, "id", None)
            attr = getattr(base, "attr", None)
            if name == "BaseDetector" or attr == "BaseDetector":
                has_detector = True
    if not has_detector:
        errors.append("module must define a class inheriting from BaseDetector")

    source = path.read_text(encoding="utf-8")
    if re.search(r"\bos\.system\b|\bsubprocess\b|\bsocket\b|\burllib\.request\b", source):
        errors.append("detector must not use os.system, subprocess, or raw network calls")
    if re.search(r"\beval\s*\(|exec\s*\(", source):
        errors.append("detector must not use eval or exec")

    return errors
