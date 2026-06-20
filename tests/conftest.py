"""Use isolated model dir for detection tests."""

from __future__ import annotations

import pytest

from agentarmor.core.config import DetectionConfig
from agentarmor.detection.models.manager import ModelManager


@pytest.fixture
def detection_config(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    manager = ModelManager(model_dir)
    manager.ensure_bootstrap_models()
    cfg = DetectionConfig(model_dir=str(model_dir))
    monkeypatch.setattr(
        "agentarmor.detection.pipeline.get_model_manager",
        lambda md=None: ModelManager(str(model_dir)),
    )
    monkeypatch.setattr(
        "agentarmor.detection.models.manager.get_model_manager",
        lambda md=None: ModelManager(str(model_dir) if md is None else md),
    )
    return cfg
