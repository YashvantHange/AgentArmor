"""Benchmark API tests."""

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_and_get_benchmark(client, monkeypatch):
    async def fake_run(config, suite, targets):
        from agentarmor.benchmark.models import BenchmarkRun, BenchmarkStatus, ModelScore
        from agentarmor.benchmark.config import target_from_provider

        return BenchmarkRun(
            id="will-be-overwritten",
            suite_id="owasp-llm-v1",
            suite_name="OWASP",
            status=BenchmarkStatus.COMPLETED,
            model_scores=[
                ModelScore(
                    target=target_from_provider("openai"),
                    pass_rate=0.8,
                    risk_score=0.2,
                    rank=1,
                )
            ],
        )

    monkeypatch.setattr("agentarmor.api.routes.benchmarks.run_benchmark", fake_run)

    resp = client.post(
        "/v1/benchmarks",
        json={
            "suite": "owasp",
            "targets": [{"type": "provider", "provider": "openai", "model": "gpt-3.5-turbo"}],
        },
    )
    assert resp.status_code == 200
    benchmark_id = resp.json()["benchmark_id"]

    import time

    time.sleep(0.3)
    get_resp = client.get(f"/v1/benchmarks/{benchmark_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["suite_id"] == "owasp-llm-v1"
    assert len(data["model_scores"]) == 1
