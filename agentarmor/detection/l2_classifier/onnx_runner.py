"""DeBERTa-v3 ONNX security classifier."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from agentarmor.detection.l2_classifier.fallback import L2_CLASSES, L2Result, classify_fallback

logger = logging.getLogger(__name__)


@dataclass
class L2OnnxResult(L2Result):
    engine: str = "onnx"


def classify(text: str, model_dir=None) -> L2Result:
    from agentarmor.detection.models.manager import get_model_manager
    from agentarmor.detection.models.tokenizer_utils import (
        has_tokenizer_bundle,
        warn_missing_tokenizer,
    )

    manager = get_model_manager(model_dir)
    if not manager.has_onnx_classifier():
        return classify_fallback(text)

    if not has_tokenizer_bundle(manager.model_dir, "deberta_onnx"):
        warn_missing_tokenizer("deberta_onnx")
        result = classify_fallback(text)
        result.engine = "fallback-no-tokenizer"
        return result

    try:
        return _classify_onnx(text, manager)
    except Exception as exc:
        logger.debug("L2 ONNX failed: %s", exc)
        result = classify_fallback(text)
        result.engine = "fallback-onnx-error"
        return result


def _classify_onnx(text: str, manager) -> L2OnnxResult:
    import time

    import onnxruntime as ort

    from agentarmor.detection.models.tokenizer_utils import encode_text, pad_inputs_for_session

    start = time.perf_counter()
    model_path = manager.path("deberta_onnx")
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    encoded = encode_text(text, manager.model_dir, "deberta_onnx", max_length=256)
    if encoded is None:
        result = classify_fallback(text)
        result.engine = "fallback-no-tokenizer"
        return result

    feeds = pad_inputs_for_session(session, encoded)
    outputs = session.run(None, feeds)
    logits = outputs[0].flatten()[: len(L2_CLASSES)]
    exp = np.exp(logits - np.max(logits))
    probs = exp / exp.sum()
    scores = {cls: float(probs[i]) for i, cls in enumerate(L2_CLASSES)}
    top_class = max(scores, key=scores.get)  # type: ignore[arg-type]
    latency_ms = (time.perf_counter() - start) * 1000
    return L2OnnxResult(
        scores=scores,
        max_score=scores[top_class],
        top_class=top_class,
        latency_ms=latency_ms,
        engine="onnx",
    )
