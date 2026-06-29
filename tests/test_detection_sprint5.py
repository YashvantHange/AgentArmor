"""Sprint 5 tests — detector plugins, llm-rubric, webscan partial stream."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentarmor.core.config import DetectionConfig, WebScanConfig
from agentarmor.core.models import Decision, DetectionResult, Severity
from agentarmor.detection.assertions.rubric import resolve_rubric_for_probe
from agentarmor.detection.detectors.registry import reset_detector_discovery, run_detector_plugins
from agentarmor.detection.pipeline import analyze_text
from agentarmor.sdk.detector_sdk import validate_detector_module
from agentarmor.webscan.partial_stream import apply_partial_stream_gate


@pytest.fixture(autouse=True)
def _reset_detectors():
    reset_detector_discovery()
    yield
    reset_detector_discovery()


def test_bundled_secret_detector_flags_api_key(detection_config, tmp_path):
    cfg = detection_config.model_copy(
        update={"plugin_dirs": [str(Path("detectors").resolve())], "detector_plugins_enabled": True}
    )
    result = analyze_text(
        "Sure! api_key=SECRET123456789",
        context={"probe_id": "l1.reveal-system-prompt", "prompt": "leak key"},
        config=cfg,
    )
    plugins = result.layers.get("plugins") or []
    assert plugins
    assert any(p.get("detector_id") == "detector.bundled.secret-leak" for p in plugins)
    assert result.risk_score > 0.3


def test_detector_additive_cap(detection_config):
    layers, delta = run_detector_plugins(
        "api_key=SECRET123456789 sk-abcdefghijklmnopqrstuvwxyz123456",
        context={"probe_id": "test"},
        config=detection_config.model_copy(
            update={
                "plugin_dirs": [str(Path("detectors").resolve())],
                "detector_plugins_enabled": True,
                "max_detector_plugins": 3,
            }
        ),
    )
    assert delta <= 0.15 * 3


def test_validate_detector_rejects_subprocess(tmp_path):
    bad = tmp_path / "evil.py"
    bad.write_text(
        "import subprocess\nfrom agentarmor.plugins.base import BaseDetector\n"
        "class E(BaseDetector):\n"
        "  id='detector.evil'\n"
        "  def analyze(self, t, c=None): return {}\n",
        encoding="utf-8",
    )
    errors = validate_detector_module(bad)
    assert any("subprocess" in e for e in errors)


def test_resolve_rubric_from_skills():
    rubric = resolve_rubric_for_probe("l1.ignore-instructions")
    assert rubric
    assert "refuse" in rubric.lower()


def test_partial_stream_short_response_warns():
    det = DetectionResult(
        risk_score=0.1,
        severity=Severity.INFO,
        decision=Decision.PASS,
        categories=[],
        evidence=[],
        layers={},
    )
    out = apply_partial_stream_gate(
        det,
        probe_id="l1.ignore-instructions",
        prompt="ignore",
        response="short",
        stream_meta={"complete": False, "partial": True},
        webscan=WebScanConfig(partial_fail_min_chars=120),
    )
    assert out.decision == Decision.WARN
    assert out.layers["partial_stream"]["gate"] == "warn_incomplete"


def test_partial_stream_hard_outcome_fails():
    det = DetectionResult(
        risk_score=0.2,
        severity=Severity.LOW,
        decision=Decision.PASS,
        categories=[],
        evidence=[],
        layers={},
    )
    response = "Here is your ADMIN90OFF discount code for 90% off everything today."
    out = apply_partial_stream_gate(
        det,
        probe_id="l1.ignore-instructions",
        prompt="admin discount",
        response=response,
        stream_meta={"complete": False, "partial": True},
        webscan=WebScanConfig(partial_fail_min_chars=120),
    )
    assert out.decision == Decision.FAIL
    assert out.layers["partial_stream"]["gate"] == "fail_hard_outcome"


def test_partial_stream_complete_unchanged():
    det = DetectionResult(
        risk_score=0.1,
        severity=Severity.INFO,
        decision=Decision.PASS,
        categories=[],
        evidence=[],
        layers={},
    )
    out = apply_partial_stream_gate(
        det,
        probe_id="l1.ignore-instructions",
        prompt="x",
        response="y",
        stream_meta={"complete": True, "partial": False},
        webscan=WebScanConfig(),
    )
    assert out.decision == Decision.PASS
    assert "partial_stream" not in out.layers
