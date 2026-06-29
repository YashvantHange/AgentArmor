"""Detector plugin discovery and additive scoring."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from agentarmor.core.config import DetectionConfig
from agentarmor.plugins.base import BaseDetector, _load_module_from_path, get_registered_detectors
from agentarmor.sdk.detector_sdk import MAX_RISK_DELTA, LayerContribution

logger = logging.getLogger(__name__)

_TRUST_BUNDLED = "bundled"
_TRUST_LOCAL = "local"
_TRUST_MARKETPLACE = "marketplace"

_LOADED = False


def reset_detector_discovery() -> None:
    global _LOADED
    _LOADED = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _marketplace_trusted(install_path: Path) -> bool:
    manifest = install_path / "manifest.json"
    if not manifest.exists():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return bool(data.get("trusted"))
    except Exception:
        return False


def discover_detector_plugins(plugin_dirs: list[str] | None) -> None:
    global _LOADED
    if _LOADED:
        return
    root = _repo_root()
    dirs = plugin_dirs or ["detectors"]
    for dir_name in dirs:
        plugin_dir = Path(dir_name) if Path(dir_name).is_absolute() else root / dir_name
        if not plugin_dir.is_dir():
            continue
        for py_file in sorted(plugin_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            before = set(get_registered_detectors())
            try:
                _load_module_from_path(py_file)
            except Exception:
                continue
            for detector_id in set(get_registered_detectors()) - before:
                cls = get_registered_detectors()[detector_id]
                cls.__module_file__ = str(py_file)  # type: ignore[attr-defined]
                cls.__plugin_dir__ = str(plugin_dir)  # type: ignore[attr-defined]
    _LOADED = True


def _trust_for_detector(detector_id: str, cls: type[BaseDetector]) -> str | None:
    if detector_id.startswith("detector.bundled."):
        return _TRUST_BUNDLED
    plugin_dir = getattr(cls, "__plugin_dir__", "") or ""
    path = Path(plugin_dir) if plugin_dir else None
    if path and "marketplace" in str(path).replace("\\", "/"):
        return _TRUST_MARKETPLACE if _marketplace_trusted(path) else None
    return _TRUST_LOCAL


def run_detector_plugins(
    text: str,
    *,
    context: dict[str, Any] | None,
    config: DetectionConfig,
) -> tuple[list[dict[str, Any]], float]:
    """Run enabled detector plugins; contributions are additive only (max +0.15 each)."""
    if not config.detector_plugins_enabled:
        return [], 0.0

    ctx = context or {}
    plugin_dirs = list(config.plugin_dirs or ["detectors"])
    discover_detector_plugins(plugin_dirs)

    contributions: list[LayerContribution] = []
    total_delta = 0.0
    max_plugins = max(1, config.max_detector_plugins)

    for detector_id, cls in sorted(get_registered_detectors().items()):
        if len(contributions) >= max_plugins:
            break
        trust = _trust_for_detector(detector_id, cls)
        if trust is None:
            continue
        if trust == _TRUST_MARKETPLACE and detector_id not in config.trusted_detector_ids:
            continue

        try:
            instance: BaseDetector = cls()
            start = time.perf_counter()
            raw = instance.analyze(text, ctx)
            latency_ms = (time.perf_counter() - start) * 1000
        except Exception as exc:
            logger.warning("detector %s failed: %s", detector_id, exc)
            continue

        if not isinstance(raw, dict):
            continue
        delta = min(MAX_RISK_DELTA, max(0.0, float(raw.get("risk_delta", raw.get("score", 0)))))
        if delta <= 0:
            continue
        evidence = str(raw.get("evidence", "") or raw.get("detail", ""))
        contributions.append(
            LayerContribution(
                detector_id=detector_id,
                risk_delta=delta,
                evidence=evidence,
                trust=trust,
                latency_ms=latency_ms,
            )
        )
        total_delta += delta

    total_delta = min(MAX_RISK_DELTA * max_plugins, total_delta)
    return [c.to_dict() for c in contributions], total_delta
