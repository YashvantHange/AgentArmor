"""Use isolated model dir for detection tests."""

from __future__ import annotations

import pytest

from agentarmor.core.config import DetectionConfig
from agentarmor.detection.models.manager import ModelManager


@pytest.fixture(autouse=True)
def _analysis_api_key(monkeypatch):
    """Multi-agent analysis is mandatory and requires an analysis API key. Provide a
    dummy key by default so scan entry points pass their preflight; tests that need
    the missing-key path clear it explicitly."""
    monkeypatch.setenv("AGENTARMOR_ANALYSIS_API_KEY", "test-analysis-key")


@pytest.fixture(autouse=True)
def _block_real_llm_calls(monkeypatch):
    """Prevent any real network LLM call during tests. Cloud code paths handle the
    failure by falling back to offline scoring, keeping the suite fast and offline.
    Tests that exercise the cloud path patch ``litellm.acompletion`` themselves,
    which overrides this within their own scope."""
    async def _blocked(*_args, **_kwargs):
        raise RuntimeError("litellm.acompletion is blocked during tests")

    monkeypatch.setattr("litellm.acompletion", _blocked, raising=False)


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
