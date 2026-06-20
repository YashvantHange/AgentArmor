"""Remote detection API client for api/hybrid modes."""

from __future__ import annotations

import httpx

from agentarmor.core.config import DetectionConfig
from agentarmor.core.models import DetectionResult, Decision, Severity


async def analyze_remote(
    text: str,
    prompt: str = "",
    probe_id: str = "manual",
    config: DetectionConfig | None = None,
) -> DetectionResult:
    cfg = config or DetectionConfig()
    url = f"{cfg.api_url.rstrip('/')}/v1/detection/analyze"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            json={"text": text, "prompt": prompt, "probe_id": probe_id},
        )
        response.raise_for_status()
        data = response.json()
    return _dict_to_detection_result(data)


def _dict_to_detection_result(data: dict) -> DetectionResult:
    return DetectionResult(
        risk_score=float(data.get("risk_score", 0)),
        severity=Severity(data.get("severity", "INFO")),
        decision=Decision(data.get("decision", "PASS")),
        categories=data.get("categories", []),
        evidence=data.get("evidence", []),
        layers=data.get("layers", {}),
    )
