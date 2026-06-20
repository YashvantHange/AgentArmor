"""Detection API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agentarmor.core.config import DetectionConfig, load_config
from agentarmor.core.models import DetectionResult
from agentarmor.detection.l1_signatures import scan as l1_scan
from agentarmor.detection.l2_classifier.onnx_runner import classify as l2_classify
from agentarmor.detection.l3_semantic.faiss_index import search as l3_search
from agentarmor.detection.l4_structural import analyze as l4_analyze
from agentarmor.detection.meta.xgb_scorer import score_meta
from agentarmor.detection.pipeline import analyze_text_async
from agentarmor.detection.models.manager import get_model_manager

router = APIRouter(prefix="/v1/detection", tags=["detection"])


class TextRequest(BaseModel):
    text: str
    prompt: str = ""
    probe_id: str = "manual"


class AnalyzeRequest(TextRequest):
    pass


class MetaRequest(BaseModel):
    l1_score: float = 0.0
    l2_scores: dict[str, float] = Field(default_factory=dict)
    l3_score: float = 0.0
    l4_score: float = 0.0


def _get_detection_config() -> DetectionConfig:
    import os
    from pathlib import Path

    path = Path(os.environ.get("AGENTARMOR_CONFIG", "AgentArmor.toml"))
    return load_config(path if path.exists() else None).detection


@router.post("/analyze")
async def analyze(body: AnalyzeRequest) -> dict:
    cfg = _get_detection_config()
    result = await analyze_text_async(
        body.text,
        context={"prompt": body.prompt, "probe_id": body.probe_id},
        config=cfg,
    )
    return _result_to_dict(result)


@router.post("/l1")
def detection_l1(body: TextRequest) -> dict:
    r = l1_scan(body.text)
    return {"score": r.score, "matches": r.matches, "categories": r.categories, "engine": r.engine}


@router.post("/l2")
def detection_l2(body: TextRequest) -> dict:
    cfg = _get_detection_config()
    r = l2_classify(body.text, cfg.model_dir)
    return {"scores": r.scores, "max_score": r.max_score, "top_class": r.top_class, "engine": r.engine}


@router.post("/l3")
def detection_l3(body: TextRequest) -> dict:
    cfg = _get_detection_config()
    r = l3_search(body.text, cfg.model_dir, cfg.l3_similarity_threshold)
    return {"score": r.score, "matches": r.matches, "engine": r.engine}


@router.post("/l4")
def detection_l4(body: TextRequest) -> dict:
    r = l4_analyze(body.text, prompt=body.prompt, probe_id=body.probe_id)
    return {"score": r.score, "components": r.components, "evidence": r.evidence}


@router.post("/meta")
def detection_meta(body: MetaRequest) -> dict:
    cfg = _get_detection_config()
    from agentarmor.detection.l1_signatures import L1Result
    from agentarmor.detection.l2_classifier.fallback import L2Result, L2_CLASSES
    from agentarmor.detection.l3_semantic.faiss_index import L3Result
    from agentarmor.detection.l4_structural import L4Result

    scores = {c: body.l2_scores.get(c, 0.0) for c in L2_CLASSES}
    l1 = L1Result(score=body.l1_score, matches=[], categories=[], engine="api")
    l2 = L2Result(scores=scores, max_score=max(scores.values()) if scores else 0.0, top_class=max(scores, key=scores.get) if scores else "prompt_injection", engine="api")  # noqa: E501
    l3 = L3Result(score=body.l3_score, matches=[], engine="api")
    l4 = L4Result(score=body.l4_score)
    meta = score_meta(l1, l2, l3, l4, cfg)
    return {
        "risk_score": meta.risk_score,
        "severity": meta.severity.value,
        "decision": meta.decision.value,
        "confidence": meta.confidence,
        "engine": meta.engine,
    }


@router.get("/models/status")
def models_status() -> list[dict]:
    cfg = _get_detection_config()
    manager = get_model_manager(cfg.model_dir)
    return [
        {"name": s.name, "present": s.present, "path": str(s.path) if s.path else None, "source": s.source}
        for s in manager.status()
    ]


def _result_to_dict(result: DetectionResult) -> dict:
    return {
        "risk_score": result.risk_score,
        "severity": result.severity.value,
        "decision": result.decision.value,
        "categories": result.categories,
        "evidence": result.evidence,
        "layers": result.layers,
    }
