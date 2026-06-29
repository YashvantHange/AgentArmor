"""Sprint 3 tests — judge service, rule catalog, hybrid logging."""

from __future__ import annotations

import warnings

import pytest

from agentarmor.core.config import AgenticConfig, DetectionConfig, JudgeConfig
from agentarmor.detection.judge_service import resolve_judge_mode, should_run_evidence_judge, should_run_verdict_judge
from agentarmor.detection.l1_signatures.patterns import SIGNATURE_RULES
from agentarmor.detection.l2_classifier.fallback import _RULES as L2_RULES
from agentarmor.detection.l4_structural.injection_outcomes import _OUTCOME_PATTERNS
from agentarmor.detection.pipeline import _hybrid_fetch_l2_l3
from agentarmor.detection.rules.catalog import RULE_CATALOG_VERSION, security_rules


def test_rule_catalog_version():
    assert RULE_CATALOG_VERSION
    assert len(security_rules()) >= 15


def test_l1_l2_l4_share_catalog():
    assert len(SIGNATURE_RULES) >= 11
    assert len(L2_RULES) >= 8
    assert len(_OUTCOME_PATTERNS) >= 5
    names = {r.name for r in security_rules()}
    assert "ignore_instructions" in names
    assert "admin_discount" in names


def test_judge_mode_legacy_cloud_mapping():
    cfg = DetectionConfig(
        analysis_mode="cloud",
        agentic=AgenticConfig(enabled=True, api_key="x"),
    )
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert resolve_judge_mode(cfg) == "always"
    assert should_run_verdict_judge(cfg) is True


def test_judge_mode_legacy_l5_uncertain_band():
    cfg = DetectionConfig(l5_enabled=True, analysis_mode="offline")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert resolve_judge_mode(cfg) == "uncertain_band"
    assert should_run_evidence_judge(cfg, 0.5) is True
    assert should_run_evidence_judge(cfg, 0.2) is False


def test_judge_mode_explicit_off():
    cfg = DetectionConfig(judge=JudgeConfig(mode="off"), l5_enabled=True, analysis_mode="cloud")
    assert resolve_judge_mode(cfg) == "off"
    assert should_run_verdict_judge(cfg) is False


def test_hybrid_fetch_logs_fallback(monkeypatch):
    from agentarmor.detection.l2_classifier.fallback import L2Result
    from agentarmor.detection.l3_semantic.faiss_index import L3Result

    cfg = DetectionConfig(mode="hybrid", api_url="http://127.0.0.1:1")

    class BoomClient:
        def __init__(self, *a, **k):
            raise ConnectionError("refused")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("httpx.Client", BoomClient)
    l2, l3, meta = _hybrid_fetch_l2_l3("test", cfg, L2Result(), L3Result(score=0.0, matches=[]))
    assert meta["fallback"] is True
    assert "error" in meta
