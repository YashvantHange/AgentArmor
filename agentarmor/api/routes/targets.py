"""Target connection test API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentarmor.core.config import AppConfig, apply_analysis_options, apply_endpoint_options, load_config, merge_cli_target
from agentarmor.core.models import ProbeRequest, TargetType
from agentarmor.engines.endpoint.client import EndpointClient
from agentarmor.engines.provider.adapter import send_probe as provider_send_probe
from agentarmor.engines.router import validate_target

router = APIRouter(prefix="/v1/targets", tags=["targets"])


class ConnectionTestRequest(BaseModel):
    target_type: str = "endpoint"
    url: str | None = None
    provider: str | None = None
    model: str | None = None
    auth_token: str | None = None
    endpoint_profile: str | None = "auto"
    request_template: str | None = None
    response_path: str | None = None


def _build_config(body: ConnectionTestRequest) -> AppConfig:
    cfg = load_config(None)
    ttype = body.target_type.lower()
    if ttype == "endpoint":
        cfg = merge_cli_target(cfg, url=body.url)
    elif ttype == "provider":
        cfg = merge_cli_target(cfg, provider=body.provider, model=body.model)
    else:
        raise HTTPException(400, f"connection test not supported for: {body.target_type}")
    cfg = apply_analysis_options(cfg, auth_token=body.auth_token)
    cfg = apply_endpoint_options(
        cfg,
        endpoint_profile=body.endpoint_profile,
        request_template=body.request_template,
        response_path=body.response_path,
    )
    validate_target(cfg)
    return cfg


@router.post("/test-connection")
async def test_connection(body: ConnectionTestRequest) -> dict:
    try:
        cfg = _build_config(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if cfg.target.type == TargetType.ENDPOINT:
        client = EndpointClient(cfg.engine_endpoint)
        result = await client.chat_completion(
            cfg,
            "connection.test",
            "Connection Test",
            [],
            ProbeRequest(messages=[{"role": "user", "content": "ping"}], model=cfg.target.model),
        )
        if result.error:
            return {
                "ok": False,
                "error": result.error,
                "status_code": result.response.status_code,
                "profile": result.metadata.get("profile"),
                "hint": result.metadata.get("autodetect", {}).get("hint"),
            }
        excerpt = (result.response.content or "")[:200]
        return {
            "ok": True,
            "latency_ms": result.latency_ms,
            "sample_excerpt": excerpt,
            "status_code": result.response.status_code,
            "profile": result.metadata.get("profile"),
            "response_path": result.metadata.get("response_path"),
        }

    if cfg.target.type == TargetType.PROVIDER:
        result = await provider_send_probe(
            cfg,
            "connection.test",
            "Connection Test",
            [],
            ProbeRequest(messages=[{"role": "user", "content": "ping"}], model=cfg.target.model),
        )
        if result.error:
            return {"ok": False, "error": result.error}
        return {
            "ok": True,
            "latency_ms": result.latency_ms,
            "sample_excerpt": (result.response.content or "")[:200],
        }

    return {"ok": False, "error": "unsupported target type"}
