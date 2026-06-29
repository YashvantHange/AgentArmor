"""Active learning queue for uncertain and disagreement samples."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentarmor.core.config import DetectionConfig
from agentarmor.core.models import Decision, DetectionResult

_DEFAULT_QUEUE = Path.home() / ".agentarmor" / "review_queue.jsonl"


def review_queue_path(config: DetectionConfig | None = None) -> Path:
    if config is not None and getattr(config, "active_learning_queue_path", None):
        return Path(config.active_learning_queue_path).expanduser()
    return _DEFAULT_QUEUE


def _uncertain_band(score: float, low: float = 0.45, high: float = 0.55) -> bool:
    return low <= score <= high


def should_queue_sample(
    detection: DetectionResult,
    *,
    judge_vulnerable: bool | None = None,
    uncertain_low: float = 0.45,
    uncertain_high: float = 0.55,
) -> tuple[bool, str]:
    """Return (queue, reason)."""
    if _uncertain_band(detection.risk_score, uncertain_low, uncertain_high):
        return True, "uncertain_band"

    if judge_vulnerable is not None:
        offline_fail = detection.decision == Decision.FAIL
        if judge_vulnerable != offline_fail:
            return True, "judge_disagreement"

    return False, ""


def queue_review_sample(
    *,
    probe_id: str,
    prompt: str,
    response: str,
    detection: DetectionResult,
    reason: str,
    config: DetectionConfig | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append a labeled-training candidate to the review queue."""
    path = review_queue_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    layers = detection.layers or {}
    record = {
        "id": str(uuid.uuid4()),
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "probe_id": probe_id,
        "prompt": prompt[:2000],
        "response": response[:4000],
        "layer_outputs": {
            "l1": (layers.get("l1") or {}).get("score", 0),
            "l2": (layers.get("l2") or {}).get("max_score", 0),
            "l3": (layers.get("l3") or {}).get("score", 0),
            "l4": (layers.get("l4") or {}).get("score", 0),
            "meta": (layers.get("meta") or {}).get("risk_score", detection.risk_score),
        },
        "decision": detection.decision.value,
        "risk_score": detection.risk_score,
        "label": "uncertain",
        "label_source": "active_learning",
        **(extra or {}),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def maybe_queue_review_sample(
    *,
    probe_id: str,
    prompt: str,
    response: str,
    detection: DetectionResult,
    config: DetectionConfig,
    judge_vulnerable: bool | None = None,
    enabled: bool = True,
) -> bool:
    if not enabled:
        return False
    queue, reason = should_queue_sample(
        detection,
        judge_vulnerable=judge_vulnerable,
        uncertain_low=config.active_learning_uncertain_low,
        uncertain_high=config.active_learning_uncertain_high,
    )
    if not queue:
        return False
    queue_review_sample(
        probe_id=probe_id,
        prompt=prompt,
        response=response,
        detection=detection,
        reason=reason,
        config=config,
    )
    return True
