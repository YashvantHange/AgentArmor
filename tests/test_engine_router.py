"""Engine router tests."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, Target, TargetType
from agentarmor.engines.router import send_probe, validate_target


def test_validate_endpoint_requires_url():
    cfg = AppConfig(target=Target(type=TargetType.ENDPOINT, url=None))
    with pytest.raises(ValueError, match="URL"):
        validate_target(cfg)


def test_validate_provider_requires_provider():
    cfg = AppConfig(target=Target(type=TargetType.PROVIDER, provider=None))
    with pytest.raises(ValueError, match="provider"):
        validate_target(cfg)


def test_validate_local_requires_model():
    cfg = AppConfig(target=Target(type=TargetType.LOCAL, model=None))
    with pytest.raises(ValueError, match="model"):
        validate_target(cfg)


def test_validate_module_agent():
    cfg = AppConfig(target=Target(type=TargetType.AGENT, agent_framework="crewai"))
    validate_target(cfg)


@pytest.mark.asyncio
async def test_router_dispatches_provider(monkeypatch):
    async def fake_provider(config, probe_id, probe_name, owasp, request):
        from agentarmor.core.models import ProbeResponse, ProbeResult

        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            owasp=owasp,
            request=request,
            response=ProbeResponse(content="ok"),
        )

    monkeypatch.setattr(
        "agentarmor.engines.router.provider_send_probe",
        fake_provider,
    )
    cfg = AppConfig(target=Target(type=TargetType.PROVIDER, provider="openai"))
    result = await send_probe(
        cfg, "x", "X", [], ProbeRequest(messages=[{"role": "user", "content": "hi"}])
    )
    assert result.response.content == "ok"
