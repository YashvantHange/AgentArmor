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
from agentarmor.detection.l1_signatures import scan as l1_scan
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
    if cfg.l5_enabled:
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
    get_model_manager(cfg.model_dir).ensure_bootstrap_models()

    l1 = l1_scan(text) if cfg.l1_enabled else _empty_l1()
    l2 = l2_classify(text, cfg.model_dir) if cfg.l2_enabled else _empty_l2()
    l3 = (
        l3_search(text, cfg.model_dir, cfg.l3_similarity_threshold)
        if cfg.l3_enabled
        else _empty_l3()
    )
    l4 = (
        l4_analyze(text, prompt=prompt_text, probe_id=probe_id)
        if cfg.l4_enabled
        else _empty_l4()
    )

    if cfg.mode == "hybrid" and cfg.api_url:
        l2, l3 = _hybrid_fetch_l2_l3(text, cfg, l2, l3)

    meta = score_meta(l1, l2, l3, l4, cfg)

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

    return DetectionResult(
        risk_score=meta.risk_score,
        severity=meta.severity,
        decision=meta.decision,
        categories=categories,
        evidence=evidence,
        layers=layers,
    )


def _hybrid_fetch_l2_l3(text, cfg, local_l2, local_l3):
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
            if r3.status_code == 200:
                d3 = r3.json()
                from agentarmor.detection.l3_semantic.faiss_index import L3Result

                local_l3 = L3Result(
                    score=float(d3.get("score", 0)),
                    matches=d3.get("matches", []),
                    engine="api",
                )
    except Exception:
        pass
    return local_l2, local_l3


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
