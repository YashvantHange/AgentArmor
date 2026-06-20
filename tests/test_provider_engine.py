"""Provider engine tests — mock LiteLLM."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, Target, TargetType
from agentarmor.engines.provider.adapter import send_probe
from agentarmor.engines.provider.litellm_client import SUPPORTED_PROVIDERS, resolve_model


def test_resolve_model_defaults():
    assert resolve_model("openai", None) == "gpt-3.5-turbo"
    assert resolve_model("anthropic", None).startswith("anthropic/")


def test_resolve_model_override():
    assert resolve_model("openai", "gpt-4") == "gpt-4"
    assert resolve_model("anthropic", "claude-3-opus") == "anthropic/claude-3-opus"


def test_supported_providers():
    assert "openai" in SUPPORTED_PROVIDERS
    assert "gemini" in SUPPORTED_PROVIDERS


@pytest.mark.asyncio
async def test_provider_send_probe_mock(monkeypatch):
    async def fake_completion(provider, messages, *, model=None, temperature=0.7):
        return "I cannot help with that.", {"model": model, "choices": []}, 12.5

    monkeypatch.setattr(
        "agentarmor.engines.provider.adapter.completion",
        fake_completion,
    )
    config = AppConfig(
        target=Target(type=TargetType.PROVIDER, provider="openai", model="gpt-3.5-turbo"),
    )
    request = ProbeRequest(messages=[{"role": "user", "content": "test"}])
    result = await send_probe(config, "l1.test", "Test", ["LLM01"], request)
    assert result.error is None
    assert "cannot" in result.response.content.lower()
    assert result.metadata["provider"] == "openai"
