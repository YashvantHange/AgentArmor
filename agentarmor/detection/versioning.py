"""Detector version stamps for scan reproducibility."""

from __future__ import annotations

from agentarmor.core.config import DetectionConfig
from agentarmor.detection.judge_service import resolve_judge_mode
from agentarmor.detection.rules.catalog import RULE_CATALOG_VERSION


def build_detector_version_stamp(config: DetectionConfig, layers: dict | None = None) -> dict[str, str]:
    """Collect versions of all components that influenced a detection verdict."""
    layers = layers or {}
    meta = layers.get("meta") if isinstance(layers.get("meta"), dict) else {}
    meta_engine = str(meta.get("engine", "unknown"))

    embedder = "unknown"
    try:
        from agentarmor.detection.models.manager import get_model_manager

        manifest = get_model_manager(config.model_dir).read_manifest()
        embedder_info = manifest.get("embedder") or {}
        if isinstance(embedder_info, dict):
            embedder = str(embedder_info.get("version") or embedder_info.get("name") or "unknown")
        fp = get_model_manager(config.model_dir).embedder_fingerprint()
        if fp:
            embedder = fp
    except Exception:
        pass

    judge_mode = resolve_judge_mode(config)
    if judge_mode == "off":
        judge = "off"
    else:
        judge = f"{config.agentic.model}:{judge_mode}"

    plugins = layers.get("plugins") if isinstance(layers.get("plugins"), list) else []
    plugin_ids = ",".join(sorted({str(p.get("detector_id", "")) for p in plugins if p})) or "none"

    return {
        "rule_catalog": RULE_CATALOG_VERSION,
        "embedder": embedder,
        "meta": meta_engine,
        "judge": judge,
        "plugins": plugin_ids,
    }
