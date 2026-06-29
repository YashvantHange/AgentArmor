"""
Full detection pipeline: L1 → L2 → L3 → L4 → Meta → (optional L5).

Supports local, api, and hybrid modes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agentarmor.core.config import DetectionConfig
from agentarmor.core.models import (
    Decision,
    DetectionResult,
    ProbeRequest,
    ProbeResponse,
    ProbeResult,
    Severity,
)
from agentarmor.detection.rules.catalog import RULE_CATALOG_VERSION
from agentarmor.detection.l1_signatures import scan_with_echo_filter
from agentarmor.detection.l2_classifier.onnx_runner import classify as l2_classify
from agentarmor.detection.l3_semantic.faiss_index import search as l3_search
from agentarmor.detection.l4_structural import analyze as l4_analyze
from agentarmor.detection.meta.xgb_scorer import score_meta
from agentarmor.detection.models.manager import get_model_manager

_DEFAULT_DETECTION = DetectionConfig()


def analyze_probe_result(
    probe: ProbeResult,
    prompt_text: str = "",
    config: DetectionConfig | None = None,
) -> DetectionResult:
    cfg = config or _DEFAULT_DETECTION

    if probe.error:
        return _error_result(probe.error)

    if cfg.mode == "api":
        return asyncio.run(
            _analyze_api_mode(probe.response.content or "", prompt_text, probe.probe_id, cfg)
        )

    return _analyze_local(probe.response.content or "", prompt_text, probe.probe_id, cfg)


async def analyze_probe_result_async(
    probe: ProbeResult,
    prompt_text: str = "",
    config: DetectionConfig | None = None,
) -> DetectionResult:
    cfg = config or _DEFAULT_DETECTION
    if probe.error:
        return _error_result(probe.error)
    if cfg.mode == "api":
        from agentarmor.detection.client import analyze_remote

        return await analyze_remote(
            probe.response.content or "",
            prompt_text,
            probe.probe_id,
            cfg,
        )
    result = _analyze_local(probe.response.content or "", prompt_text, probe.probe_id, cfg)
    from agentarmor.detection.judge_service import judge_pipeline_evidence, resolve_judge_mode

    if resolve_judge_mode(cfg) == "uncertain_band":
        result = await _maybe_judge(result, probe.response.content or "", prompt_text, cfg)
    return result


def analyze_text(
    text: str,
    context: dict[str, Any] | None = None,
    config: DetectionConfig | None = None,
) -> DetectionResult:
    ctx = context or {}
    fake = ProbeResult(
        probe_id=str(ctx.get("probe_id", "manual")),
        probe_name=str(ctx.get("probe_name", "manual")),
        request=ProbeRequest(messages=[{"role": "user", "content": ctx.get("prompt", "")}]),
        response=ProbeResponse(content=text),
    )
    return analyze_probe_result(fake, prompt_text=str(ctx.get("prompt", "")), config=config)


async def analyze_text_async(
    text: str,
    context: dict[str, Any] | None = None,
    config: DetectionConfig | None = None,
) -> DetectionResult:
    ctx = context or {}
    fake = ProbeResult(
        probe_id=str(ctx.get("probe_id", "manual")),
        probe_name=str(ctx.get("probe_name", "manual")),
        request=ProbeRequest(messages=[{"role": "user", "content": ctx.get("prompt", "")}]),
        response=ProbeResponse(content=text),
    )
    return await analyze_probe_result_async(
        fake, prompt_text=str(ctx.get("prompt", "")), config=config
    )


def _analyze_local(
    text: str,
    prompt_text: str,
    probe_id: str,
    cfg: DetectionConfig,
) -> DetectionResult:
    import time

    get_model_manager(cfg.model_dir).ensure_bootstrap_models()

    echo_strip_ms = 0.0
    scoring_text = text
    echo_layers: dict = {"enabled": False}

    if cfg.experimental.echo_aware_l1_l2 and prompt_text:
        from agentarmor.detection.l4_structural.echo import (
            find_echo_spans,
            should_strip_echo_for_scoring,
            strip_echo_spans,
        )

        t0 = time.perf_counter()
        spans = find_echo_spans(
            prompt_text, text, min_len=cfg.experimental.echo_min_span_len
        )
        scoring_text = (
            strip_echo_spans(text, spans)
            if should_strip_echo_for_scoring(prompt_text, spans)
            else text
        )
        echo_strip_ms = (time.perf_counter() - t0) * 1000
        echo_layers = {
            "enabled": True,
            "span_count": len(spans),
            "latency_ms": echo_strip_ms,
            "strip_applied": scoring_text != text,
            "spans": [{"start": s.start, "end": s.end} for s in spans],
        }
    else:
        spans = []

    l1 = (
        scan_with_echo_filter(text, spans if spans else None)
        if cfg.l1_enabled
        else _empty_l1()
    )
    l2 = l2_classify(scoring_text, cfg.model_dir) if cfg.l2_enabled else _empty_l2()
    l3 = (
        l3_search(scoring_text, cfg.model_dir, cfg.l3_similarity_threshold)
        if cfg.l3_enabled
        else _empty_l3()
    )
    l4 = (
        l4_analyze(
            text,
            prompt=prompt_text,
            probe_id=probe_id,
            tiered_compliance=cfg.experimental.tiered_compliance,
        )
        if cfg.l4_enabled
        else _empty_l4()
    )

    if cfg.mode == "hybrid" and cfg.api_url:
        l2, l3, hybrid_meta = _hybrid_fetch_l2_l3(scoring_text, cfg, l2, l3)
        if hybrid_meta:
            echo_layers = {**echo_layers, "hybrid": hybrid_meta}

    meta = score_meta(l1, l2, l3, l4, cfg, probe_id=probe_id)

    from agentarmor.detection.detectors.registry import run_detector_plugins

    plugin_layers, plugin_risk = run_detector_plugins(
        text,
        context={"probe_id": probe_id, "prompt": prompt_text},
        config=cfg,
    )
    if plugin_risk > 0:
        from agentarmor.detection.probe_thresholds import resolve_probe_thresholds

        thr = resolve_probe_thresholds(probe_id, cfg)
        meta.risk_score = min(1.0, meta.risk_score + plugin_risk)
        if meta.risk_score >= thr.fail_threshold:
            meta.decision = Decision.FAIL
            meta.severity = Severity.HIGH
        elif meta.risk_score >= thr.warn_threshold and meta.decision == Decision.PASS:
            meta.decision = Decision.WARN
            meta.severity = Severity.MEDIUM

    evidence: list[str] = []
    if l1.matches:
        evidence.extend(f"L1 match: {m}" for m in l1.matches)
    if l2.max_score > 0.3:
        evidence.append(f"L2 top class: {l2.top_class} ({l2.max_score:.2f})")
    if l3.matches:
        evidence.append(f"L3 semantic match: {l3.matches[0][:80]}")
    evidence.extend(l4.evidence)

    categories = list(
        dict.fromkeys(
            l1.categories
            + ([l2.top_class] if l2.max_score > 0.3 else [])
            + list(l4.components.keys())
        )
    )

    layers = {
        "echo_strip": echo_layers,
        "rule_catalog": RULE_CATALOG_VERSION,
        "l1": _layer_dict(l1),
        "l2": {"scores": l2.scores, "max_score": l2.max_score, "top_class": l2.top_class, "engine": l2.engine, "latency_ms": l2.latency_ms},
        "l3": {"score": l3.score, "matches": l3.matches, "engine": l3.engine, "latency_ms": l3.latency_ms},
        "l4": {"score": l4.score, "components": l4.components, "latency_ms": l4.latency_ms},
        "meta": {
            "risk_score": meta.risk_score,
            "confidence": meta.confidence,
            "engine": meta.engine,
            "latency_ms": meta.latency_ms,
        },
    }
    if plugin_layers:
        layers["plugins"] = plugin_layers
        evidence.extend(
            f"plugin {p['detector_id']}: {p.get('evidence', '')[:80]}"
            for p in plugin_layers
            if p.get("evidence")
        )

    from agentarmor.detection.evidence.spans import collect_evidence_spans

    all_spans = collect_evidence_spans(layers)
    if all_spans:
        layers["evidence_spans"] = all_spans

    return DetectionResult(
        risk_score=meta.risk_score,
        severity=meta.severity,
        decision=meta.decision,
        categories=categories,
        evidence=evidence,
        layers=layers,
    )


def _hybrid_fetch_l2_l3(text, cfg, local_l2, local_l3):
    import logging

    logger = logging.getLogger(__name__)
    meta: dict = {"fallback": False, "l2_from_api": False, "l3_from_api": False}
    try:
        import httpx

        base = cfg.api_url.rstrip("/")
        with httpx.Client(timeout=30.0) as client:
            r2 = client.post(f"{base}/v1/detection/l2", json={"text": text})
            r3 = client.post(f"{base}/v1/detection/l3", json={"text": text})
            if r2.status_code == 200:
                d2 = r2.json()
                from agentarmor.detection.l2_classifier.fallback import L2Result

                local_l2 = L2Result(
                    scores=d2.get("scores", {}),
                    max_score=float(d2.get("max_score", 0)),
                    top_class=d2.get("top_class", "prompt_injection"),
                    engine="api",
                )
                meta["l2_from_api"] = True
            if r3.status_code == 200:
                d3 = r3.json()
                from agentarmor.detection.l3_semantic.faiss_index import L3Result

                local_l3 = L3Result(
                    score=float(d3.get("score", 0)),
                    matches=d3.get("matches", []),
                    engine="api",
                )
                meta["l3_from_api"] = True
    except Exception as exc:
        meta["fallback"] = True
        meta["error"] = str(exc)
        logger.warning("hybrid L2/L3 API fetch failed, using local fallback: %s", exc)
    return local_l2, local_l3, meta


async def _analyze_api_mode(text: str, prompt: str, probe_id: str, cfg: DetectionConfig) -> DetectionResult:
    from agentarmor.detection.client import analyze_remote

    return await analyze_remote(text, prompt, probe_id, cfg)


async def _maybe_judge(
    result: DetectionResult,
    text: str,
    prompt: str,
    cfg: DetectionConfig,
) -> DetectionResult:
    from agentarmor.detection.l5_judge.judge import judge_evidence

    judged = await judge_evidence(text, prompt, result.risk_score, cfg)
    if judged and judged.invoked:
        result.evidence = list(result.evidence) + [f"L5 judge: {judged.explanation}"]
        result.layers = dict(result.layers)
        result.layers["l5"] = {
            "explanation": judged.explanation,
            "latency_ms": judged.latency_ms,
        }
    return result


def _error_result(error: str) -> DetectionResult:
    return DetectionResult(
        risk_score=0.2,
        severity=Severity.MEDIUM,
        decision=Decision.WARN,
        evidence=[f"connectivity: {error}"],
        layers={"error": error, "connectivity": True},
        categories=["connectivity"],
    )


def _layer_dict(l1) -> dict:
    return {
        "score": l1.score,
        "matches": l1.matches,
        "categories": l1.categories,
        "engine": l1.engine,
        "latency_ms": l1.latency_ms,
        "evidence_spans": list(getattr(l1, "evidence_spans", None) or []),
    }


def _empty_l1():
    from agentarmor.detection.l1_signatures import L1Result

    return L1Result(score=0.0, matches=[], categories=[], engine="disabled")


def _empty_l2():
    from agentarmor.detection.l2_classifier.fallback import L2Result

    return L2Result(scores={}, max_score=0.0, engine="disabled")


def _empty_l3():
    from agentarmor.detection.l3_semantic.faiss_index import L3Result

    return L3Result(score=0.0, matches=[], engine="disabled")


def _empty_l4():
    from agentarmor.detection.l4_structural import L4Result

    return L4Result(score=0.0)
