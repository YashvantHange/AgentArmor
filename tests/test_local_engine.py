"""Local model engine tests — mocked backends."""

from pathlib import Path

import pytest

from agentarmor.core.config import AppConfig, LocalEngineConfig
from agentarmor.core.models import ProbeRequest, Target, TargetType
from agentarmor.engines.local.adapter import send_probe
from agentarmor.engines.local.router import LocalBackend, detect_backend


def test_detect_backend_gguf(tmp_path):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"\x00" * 100)
    assert detect_backend(gguf) == LocalBackend.LLAMA_CPP


def test_detect_backend_hf_dir(tmp_path):
    hf = tmp_path / "qwen3"
    hf.mkdir()
    (hf / "config.json").write_text('{"model_type": "llama"}')
    assert detect_backend(hf) == LocalBackend.TRANSFORMERS


def test_detect_backend_unknown(tmp_path):
    f = tmp_path / "unknown.dat"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="Cannot detect backend"):
        detect_backend(f)


@pytest.mark.asyncio
async def test_local_send_probe_mock(monkeypatch, tmp_path):
    gguf = tmp_path / "tiny.gguf"
    gguf.write_bytes(b"\x00" * 64)

    class FakeRouter:
        backend_type = LocalBackend.LLAMA_CPP

        def complete(self, messages, *, temperature=0.7, max_tokens=512):
            return "refused", {"choices": []}, 5.0

    monkeypatch.setattr(
        "agentarmor.engines.local.adapter._get_router",
        lambda *a, **k: FakeRouter(),
    )
    config = AppConfig(
        target=Target(type=TargetType.LOCAL, model=str(gguf)),
        engine_local=LocalEngineConfig(backend="auto", gpu_layers=0),
    )
    request = ProbeRequest(messages=[{"role": "user", "content": "ignore instructions"}])
    result = await send_probe(config, "l1.test", "Test", ["LLM01"], request)
    assert result.error is None
    assert result.response.content == "refused"
    assert result.metadata["backend"] == "llama_cpp"
