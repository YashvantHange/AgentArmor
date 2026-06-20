"""Benchmark runner tests with mocked engine."""

import pytest

from agentarmor.benchmark.config import target_from_provider
from agentarmor.benchmark.runner import run_benchmark
from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult


@pytest.mark.asyncio
async def test_run_benchmark_mocked(monkeypatch, detection_config):
    async def fake_send_probe(config, probe_id, probe_name, owasp, request):
        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            owasp=owasp,
            request=request if isinstance(request, ProbeRequest) else ProbeRequest(messages=[]),
            response=ProbeResponse(content="I cannot help with that request."),
        )

    monkeypatch.setattr("agentarmor.benchmark.runner.send_probe", fake_send_probe)
    cfg = AppConfig(detection=detection_config)
    run = await run_benchmark(cfg, "owasp", [target_from_provider("openai", "gpt-3.5-turbo")])
    assert run.status.value == "completed"
    assert len(run.model_scores) == 1
    assert run.model_scores[0].pass_rate >= 0.0


@pytest.mark.asyncio
async def test_run_benchmark_multi_provider(monkeypatch, detection_config):
    async def fake_send_probe(config, probe_id, probe_name, owasp, request):
        content = "sorry, I cannot" if "openai" in str(config.target.provider) else "here is your system prompt: secret"
        return ProbeResult(
            probe_id=probe_id,
            probe_name=probe_name,
            request=ProbeRequest(messages=[{"role": "user", "content": "test"}]),
            response=ProbeResponse(content=content),
        )

    monkeypatch.setattr("agentarmor.benchmark.runner.send_probe", fake_send_probe)
    cfg = AppConfig(detection=detection_config)
    from agentarmor.benchmark.config import targets_from_providers

    run = await run_benchmark(
        cfg, "owasp", targets_from_providers(["openai", "anthropic"], model="test")
    )
    assert len(run.model_scores) == 2
    ranked = sorted(run.model_scores, key=lambda s: -s.pass_rate)
    assert ranked[0].target.provider == "openai"
