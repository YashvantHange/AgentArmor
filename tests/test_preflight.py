"""Tests for the analysis-key preflight validation."""

from __future__ import annotations

import pytest

from agentarmor.core.config import load_config
from agentarmor.detection.agentic.preflight import _is_auth_error, validate_analysis_key


class _AuthError(Exception):
    """Stands in for litellm.AuthenticationError (matched by class name)."""


class _Timeout(Exception):
    pass


def _cfg(key: str = "sk-test"):
    cfg = load_config()
    cfg.detection.agentic.enabled = True
    cfg.detection.agentic.api_key = key
    return cfg


def test_is_auth_error_by_name_and_status():
    assert _is_auth_error(_AuthError("Incorrect API key provided"))
    err = Exception("boom")
    err.status_code = 401  # type: ignore[attr-defined]
    assert _is_auth_error(err)
    assert not _is_auth_error(_Timeout("request timed out"))


@pytest.mark.asyncio
async def test_preflight_raises_on_auth_error(monkeypatch):
    import litellm

    async def _boom(*_a, **_k):
        raise _AuthError("Incorrect API key provided: sk-bad")

    monkeypatch.setattr(litellm, "acompletion", _boom)
    with pytest.raises(ValueError, match="rejected"):
        await validate_analysis_key(_cfg("sk-bad"))


@pytest.mark.asyncio
async def test_preflight_swallows_transient_error(monkeypatch):
    import litellm

    async def _timeout(*_a, **_k):
        raise _Timeout("connection timed out")

    monkeypatch.setattr(litellm, "acompletion", _timeout)
    # Must NOT raise — transient issues should not block a scan.
    await validate_analysis_key(_cfg())


@pytest.mark.asyncio
async def test_preflight_passes_on_success(monkeypatch):
    import litellm

    async def _ok(*_a, **_k):
        return {"choices": [{"message": {"content": "pong"}}]}

    monkeypatch.setattr(litellm, "acompletion", _ok)
    await validate_analysis_key(_cfg())


@pytest.mark.asyncio
async def test_preflight_noop_without_key():
    cfg = _cfg("")
    # No key configured -> nothing to validate here (ensure_analysis_ready guards it).
    await validate_analysis_key(cfg)
