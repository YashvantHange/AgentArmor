"""BGE ONNX embedder when model and tokenizer are downloaded."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from agentarmor.detection.models.tokenizer_utils import encode_text, pad_inputs_for_session


class BGEOnnxEmbedder:
    def __init__(self, model_path: Path, model_dir: Path) -> None:
        import onnxruntime as ort

        self._model_dir = model_dir
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    def embed(self, text: str) -> list[float]:
        encoded = encode_text(text, self._model_dir, "bge_onnx", max_length=512)
        if encoded is None:
            raise RuntimeError("BGE tokenizer bundle missing")
        feeds = pad_inputs_for_session(self._session, encoded)
        outputs = self._session.run(None, feeds)
        vec = outputs[0].flatten().tolist()
        return vec
